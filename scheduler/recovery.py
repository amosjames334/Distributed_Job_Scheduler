import asyncio
import os
from datetime import datetime, timezone
import redis.asyncio as redis
from sqlalchemy.future import select
from .database import get_db_session
from .models import Job, JobStatus

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOBS_STREAM = "jobs:pending"
WORKERS_SET = "available_workers"


async def run_recovery_loop(interval: int = 30):
    """Detect stuck jobs on dead workers and re-enqueue them."""
    print("Recovery loop started...")
    r = redis.from_url(REDIS_URL)

    while True:
        try:
            await asyncio.sleep(interval)
            print("Running recovery check...")

            async_session = get_db_session()
            async for session in async_session:
                try:
                    active_states = [
                        JobStatus.ASSIGNED,
                        JobStatus.PULLING,
                        JobStatus.INSTALLING,
                        JobStatus.RUNNING,
                    ]
                    result = await session.execute(
                        select(Job).where(Job.status.in_(active_states))
                    )
                    active_jobs = result.scalars().all()

                    for job in active_jobs:
                        if not job.assigned_worker:
                            continue

                        hb_key = f"worker:heartbeat:{job.assigned_worker}"
                        is_alive = await r.exists(hb_key)

                        if not is_alive:
                            print(f"Worker {job.assigned_worker} is DEAD. Re-enqueuing job {job.id}")
                            await r.srem(WORKERS_SET, job.assigned_worker)

                            if job.retries_left > 0:
                                job.status = JobStatus.PENDING
                                job.assigned_worker = None
                                job.retries_left -= 1
                                job.updated_at = datetime.now(timezone.utc)
                                await session.commit()
                                await r.xadd(JOBS_STREAM, {"job_id": str(job.id)})
                            else:
                                job.status = JobStatus.DEAD
                                job.error_message = "Retries exhausted after worker failure"
                                job.updated_at = datetime.now(timezone.utc)
                                await session.commit()

                    result = await session.execute(
                        select(Job).where(
                            Job.status == JobStatus.FAILED,
                            Job.retries_left > 0,
                        )
                    )
                    failed_jobs = result.scalars().all()

                    for job in failed_jobs:
                        print(f"Retrying failed job {job.id} (retries_left={job.retries_left})")
                        job.status = JobStatus.PENDING
                        job.retries_left -= 1
                        job.assigned_worker = None
                        job.updated_at = datetime.now(timezone.utc)
                        await session.commit()
                        await r.xadd(JOBS_STREAM, {"job_id": str(job.id)})

                except Exception as e:
                    print(f"Recovery error DB: {e}")
                    await session.rollback()
                finally:
                    await session.close()
                break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Recovery loop error: {e}")
            await asyncio.sleep(5)
