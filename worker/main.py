import asyncio
import os
import json
from datetime import datetime, timezone
import redis.asyncio as redis
from sqlalchemy.future import select
from minio import Minio
from prometheus_client import start_http_server

from .database import get_db_session
from .models import Job, JobStatus
from .agent import heartbeat_loop, register_worker, listen_for_jobs
from .reporter import (
    update_state, report_success, report_failure, report_cache,
    JOB_DURATION,
)
from .env_resolver import pull_bundle, resolve_image
from .runner import run_job
from .executor import DockerExecutor

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio123")
WORKERS_SET = "available_workers"
CONSUMER_NAME = os.getenv("HOSTNAME", "worker-1")
TMP_JOBS_DIR = os.getenv("TMP_JOBS_DIR", "/tmp/jobs")


def get_minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


_legacy_executor = DockerExecutor()
_minio_client = None


async def main():
    global _minio_client
    print(f"Worker {CONSUMER_NAME} starting...")

    try:
        start_http_server(8000)
        print("Worker metrics server started on 8000")
    except Exception as e:
        print(f"Failed to start metrics: {e}")

    r = redis.from_url(REDIS_URL)
    _minio_client = get_minio_client()

    await register_worker(CONSUMER_NAME, r, WORKERS_SET)

    asyncio.create_task(heartbeat_loop(CONSUMER_NAME, r))

    await listen_for_jobs(CONSUMER_NAME, r, process_job)


async def process_job(job_id: str):
    async_session = get_db_session()
    async for session in async_session:
        try:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if not job:
                print(f"Job {job_id} not found in DB")
                return

            if _check_minio_bundle(_minio_client, job_id):
                await _process_bundle_job(session, job, _minio_client)
            else:
                await _process_legacy_job(session, job, _legacy_executor)

        except Exception as e:
            print(f"Failed processing job {job_id}: {e}")
            await session.rollback()
        finally:
            await session.close()
        break


def _check_minio_bundle(minio_client: Minio, job_id: str) -> bool:
    try:
        minio_client.stat_object("jobs", f"{job_id}/script.py")
        return True
    except Exception:
        return False


async def _process_bundle_job(session, job, minio_client: Minio):
    """New pipeline: pull from MinIO, resolve env, run with bind-mount."""
    job_id = str(job.id)
    tmp_dir = os.path.join(TMP_JOBS_DIR, job_id)

    await update_state(session, job, JobStatus.PULLING, expected_status=JobStatus.ASSIGNED)

    print(f"Pulling bundle for job {job_id}...")
    await asyncio.to_thread(pull_bundle, minio_client, job_id, tmp_dir)

    manifest = {}
    try:
        resp = minio_client.get_object("jobs", f"{job_id}/manifest.json")
        manifest = json.loads(resp.read())
        resp.close()
        resp.release_conn()
    except Exception:
        pass

    base_image = manifest.get("image_base", job.image_base or "python:3.11-slim")
    req_path = os.path.join(tmp_dir, "requirements.txt")
    script_path = os.path.join(tmp_dir, "script.py")

    await update_state(session, job, JobStatus.INSTALLING)

    print(f"Resolving environment for job {job_id}...")
    image, cache_hit = await asyncio.to_thread(resolve_image, base_image, req_path)
    report_cache(cache_hit)
    print(f"Image resolved: {image} (cache_hit={cache_hit})")

    await update_state(
        session, job, JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    print(f"Running job {job_id}...")
    with JOB_DURATION.time():
        exit_code, logs = await asyncio.to_thread(run_job, job_id, image, script_path, manifest)

    if exit_code == 0:
        report_success(job, exit_code, logs)
        await update_state(session, job, JobStatus.SUCCESS)
    else:
        report_failure(job, exit_code, logs)
        await update_state(
            session, job, JobStatus.FAILED,
            error_message=logs[:2000] if logs else "Unknown error",
        )

    print(f"Job {job_id} finished: exit_code={exit_code}")


async def _process_legacy_job(session, job, executor: DockerExecutor):
    """Legacy pipeline: run command directly via Docker CLI."""
    await update_state(
        session, job, JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    command = job.command or []
    image = job.image_base or "python:3.11-slim"

    print(f"Running legacy job {job.id}: {command}")

    with JOB_DURATION.time():
        exit_code, logs = executor.run_job(image, command)

    if exit_code == 0:
        report_success(job, exit_code, logs)
        await update_state(session, job, JobStatus.SUCCESS)
    else:
        report_failure(job, exit_code, logs)
        await update_state(session, job, JobStatus.FAILED)

    print(f"Legacy job {job.id} finished with status {job.status}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker stopping...")
