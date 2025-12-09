import asyncio
import os
import signal
import sys
import json
import redis.asyncio as redis
from sqlalchemy.future import select
from .database import get_db_session, engine
from .models import Job, JobStatus
from .executor import DockerExecutor
from datetime import datetime
from prometheus_client import start_http_server, Counter, Histogram

# Metrics
JOBS_PROCESSED = Counter('jobs_processed_total', 'Jobs processed by worker', ['status'])
JOB_DURATION = Histogram('job_duration_seconds', 'Time spent processing job')

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WORKERS_SET = "available_workers"
CONSUMER_NAME = os.getenv("HOSTNAME", "worker-1")
WORKER_QUEUE = f"worker_queue:{CONSUMER_NAME}"

async def main():
    print(f"Worker {CONSUMER_NAME} starting...")
    
    # Start Metrics Server
    try:
        start_http_server(8000)
        print("Worker metrics server started on 8000")
    except Exception as e:
        print(f"Failed to start metrics: {e}")

    # 1. Connect to Redis
    r = redis.from_url(REDIS_URL)
    
    # 2. Register Worker & Start Heartbeat
    await r.sadd(WORKERS_SET, CONSUMER_NAME)
    print(f"Registered {CONSUMER_NAME} in {WORKERS_SET}")
    
    # Start Heartbeat
    heartbeat_task = asyncio.create_task(send_heartbeat(r, CONSUMER_NAME))

    # 3. Initialize Executor
    executor = DockerExecutor()

    print(f"Listening on queue {WORKER_QUEUE}...")
    while True:
        try:
            # BLPOP is blocking pop from list
            # Returns (key, element) or None if timeout
            result = await r.blpop(WORKER_QUEUE, timeout=5)
            
            if not result:
                continue

            # result is tuple (queue_name, data)
            _, job_id_bytes = result
            job_id = job_id_bytes.decode('utf-8')
            
            print(f"Received job {job_id}")
            await process_job(job_id, executor)

        except Exception as e:
            print(f"Error in worker loop: {e}")
            await asyncio.sleep(5)

async def send_heartbeat(r: redis.Redis, worker_id: str):
    while True:
        try:
            # Set a key with TTL 10s
            await r.set(f"worker:heartbeat:{worker_id}", "alive", ex=10)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Heartbeat error: {e}")
            await asyncio.sleep(5)

async def process_job(job_id: str, executor: DockerExecutor):
    async_session = get_db_session()
    async for session in async_session:
        try:
            # Fetch Job
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                print(f"Job {job_id} not found in DB")
                return

            # Update to RUNNING
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await session.commit()

            # Execute
            command = job.command
            image = job.image
            
            print(f"Running job {job_id}: {command}")
            
            with JOB_DURATION.time():
                exit_code, logs = executor.run_job(image, command)

            # Update status
            if exit_code == 0:
                job.status = JobStatus.SUCCEEDED
                JOBS_PROCESSED.labels(status='succeeded').inc()
            else:
                job.status = JobStatus.FAILED
                JOBS_PROCESSED.labels(status='failed').inc()
            
            job.finished_at = datetime.utcnow()
            await session.commit()
            print(f"Job {job_id} finished with status {job.status}")

        except Exception as e:
            print(f"Failed processing job {job_id}: {e}")
            await session.rollback()
            JOBS_PROCESSED.labels(status='error').inc()
        finally:
             await session.close()
        break 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Worker stopping...")

