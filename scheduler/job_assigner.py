import asyncio
import os
from datetime import datetime, timezone
import redis.asyncio as redis
from sqlalchemy.future import select
from .database import get_db_session
from .models import Job, JobStatus
from prometheus_client import Counter, Gauge

JOBS_SCHEDULED = Counter("jobs_scheduled_total", "Total number of jobs successfully scheduled")
ACTIVE_WORKERS = Gauge("active_workers", "Number of currently active workers")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOBS_STREAM = "jobs:pending"
SCHEDULER_GROUP = "schedulers"
SCHEDULER_CONSUMER = os.getenv("HOSTNAME", "scheduler-1")
WORKERS_SET = "available_workers"


async def run_assignment_loop():
    """Main scheduler loop: read pending jobs, assign to workers via Pub/Sub."""
    r = redis.from_url(REDIS_URL)

    try:
        await r.xgroup_create(JOBS_STREAM, SCHEDULER_GROUP, mkstream=True)
        print(f"Created consumer group {SCHEDULER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group {SCHEDULER_GROUP} already exists")
        else:
            print(f"Redis Group Error: {e}")

    print("Scheduler loop active processing jobs...")

    while True:
        try:
            streams = await r.xreadgroup(
                SCHEDULER_GROUP,
                SCHEDULER_CONSUMER,
                {JOBS_STREAM: ">"},
                count=10,
                block=2000,
            )

            if not streams:
                await asyncio.sleep(0.1)
                continue

            for stream, messages in streams:
                for message_id, data in messages:
                    job_id = data.get(b"job_id", b"").decode("utf-8")
                    if not job_id:
                        await r.xack(JOBS_STREAM, SCHEDULER_GROUP, message_id)
                        continue

                    print(f"Processing job {job_id}...")

                    workers = await r.smembers(WORKERS_SET)
                    if not workers:
                        print("No workers available! waiting...")
                        await asyncio.sleep(2)
                        continue

                    valid_workers = []
                    for w_bytes in workers:
                        w_id = w_bytes.decode("utf-8")
                        if await r.exists(f"worker:heartbeat:{w_id}"):
                            valid_workers.append(w_id)
                        else:
                            print(f"Removing dead worker from set: {w_id}")
                            await r.srem(WORKERS_SET, w_id)

                    ACTIVE_WORKERS.set(len(valid_workers))

                    if not valid_workers:
                        print("No alive workers available! waiting...")
                        await asyncio.sleep(2)
                        continue

                    worker_id = valid_workers[0]

                    if await assign_job(job_id, worker_id):
                        await r.publish(f"worker:{worker_id}:jobs", job_id)
                        JOBS_SCHEDULED.inc()
                        print(f"Assigned job {job_id} to {worker_id}")
                        await r.xack(JOBS_STREAM, SCHEDULER_GROUP, message_id)
                    else:
                        print(f"Failed to assign job {job_id}")
                        await r.xack(JOBS_STREAM, SCHEDULER_GROUP, message_id)

        except asyncio.CancelledError:
            print("Scheduler loop cancelled.")
            raise
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
            await asyncio.sleep(5)


async def assign_job(job_id: str, worker_id: str) -> bool:
    """Atomic assignment with optimistic locking."""
    async_session = get_db_session()
    async for session in async_session:
        try:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if not job:
                return False

            if job.status != JobStatus.PENDING:
                print(f"Job {job_id} is already {job.status}")
                return True

            job.assigned_worker = worker_id
            job.status = JobStatus.ASSIGNED
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return True
        except Exception as e:
            print(f"DB Error assigning job: {e}")
            await session.rollback()
            return False
        finally:
            await session.close()
        break
    return False
