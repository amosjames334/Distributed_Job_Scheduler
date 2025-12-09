import asyncio
import os
import redis.asyncio as redis
from sqlalchemy.future import select
from .database import get_db_session, get_etcd_client
from .models import Job, JobStatus
from prometheus_client import start_http_server, Counter, Gauge

# Metrics
JOBS_SCHEDULED = Counter('jobs_scheduled_total', 'Total number of jobs successfully scheduled')
ACTIVE_WORKERS = Gauge('active_workers', 'Number of currently active workers')

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOBS_STREAM = "jobs_stream"
SCHEDULER_GROUP = "scheduler_group"
SCHEDULER_CONSUMER = os.getenv("HOSTNAME", "scheduler-1")
WORKERS_SET = "available_workers"

LEADER_KEY = "/scheduler/leader"
LEASE_TTL = 10 

async def main():
    print(f"Scheduler {SCHEDULER_CONSUMER} starting...", flush=True)
    
    try:
        print("DEBUG: Attempting to start metrics server on 8000...", flush=True)
        start_http_server(8000)
        print("DEBUG: Metrics server started on port 8000", flush=True)
    except Exception as e:
        print(f"DEBUG: Failed to start metrics server: {e}", flush=True)
        import sys
        sys.exit(1)

    etcd = get_etcd_client()
    
    while True:
        try:
            # Try to acquire leadership (running blocking etcd calls in thread)
            print(f"Attempting to become leader...")
            is_leader, lease = await asyncio.to_thread(try_acquire_leadership, etcd)
            
            if is_leader:
                print(f"I am the LEADER ({SCHEDULER_CONSUMER}). Starting scheduler loop...")
                
                # Start the actual scheduling logic as a background task
                scheduler_task = asyncio.create_task(run_scheduler_loop())
                reconcile_task = asyncio.create_task(run_reconciliation_loop())
                
                # Keep renewing lease
                try:
                    while True:
                        await asyncio.to_thread(lease.refresh)
                        # Sleep less than TTL
                        await asyncio.sleep(LEASE_TTL / 3)
                except Exception as e:
                    print(f"Lost leadership/Error maintaining lease: {e}")
                finally:
                    # Clean up if we lose leadership
                    print("Stopping scheduler loop...")
                    scheduler_task.cancel()
                    reconcile_task.cancel()
                    try: 
                        await scheduler_task
                        await reconcile_task
                    except asyncio.CancelledError: 
                        pass
            else:
                # Follower loop
                print(f"I am a FOLLOWER ({SCHEDULER_CONSUMER}). Leader is active.")
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"Leader Election Error: {e}")
            await asyncio.sleep(5)

# ... (try_acquire_leadership and run_scheduler_loop remain same)

async def run_reconciliation_loop():
    print("Reconciliation loop started...")
    r = redis.from_url(REDIS_URL)
    
    while True:
        try:
            await asyncio.sleep(10) # Run every 10s
            print("Running reconciliation...")
            
            async_session = get_db_session()
            async for session in async_session:
                try:
                    # 1. Detect Dead Workers
                    # Get all RUNNING jobs
                    result = await session.execute(select(Job).where(Job.status == JobStatus.RUNNING))
                    running_jobs = result.scalars().all()
                    
                    for job in running_jobs:
                        if not job.assigned_worker: continue
                        
                        # Check Heartbeat
                        hb_key = f"worker:heartbeat:{job.assigned_worker}"
                        is_alive = await r.exists(hb_key)
                        
                        if not is_alive:
                            print(f"Worker {job.assigned_worker} is DEAD. Failing job {job.id}")
                            # Mark dead worker? Remove from set?
                            await r.srem(WORKERS_SET, job.assigned_worker)
                            
                            # Reschedule Job (Back to PENDING)
                            job.status = JobStatus.PENDING
                            job.assigned_worker = None
                            # We don't increment retry count for infra failure? Or do we?
                            # Let's treat it as a retry to be safe against poison pills crashing workers
                            job.retry_count += 1
                            await session.commit()
                    
                    # 2. Retry Failed Jobs
                    # Find FAILED jobs with retries left
                    result = await session.execute(
                        select(Job).where(
                            Job.status == JobStatus.FAILED,
                            Job.retry_count < Job.max_retries
                        )
                    )
                    failed_jobs_to_retry = result.scalars().all()
                    
                    for job in failed_jobs_to_retry:
                        print(f"Retrying failed job {job.id} (Attempt {job.retry_count + 1}/{job.max_retries})")
                        job.status = JobStatus.PENDING
                        job.retry_count += 1
                        job.assigned_worker = None
                        await session.commit()
                        
                except Exception as e:
                    print(f"Reconciliation error DB: {e}")
                    await session.rollback()
                finally:
                    await session.close()
                break # close generator
                
        except asyncio.CancelledError:
             raise
        except Exception as e:
            print(f"Reconciliation loop error: {e}")
            await asyncio.sleep(5)

def try_acquire_leadership(etcd):
    try:
        lease = etcd.lease(LEASE_TTL)
        # put_if_not_exists returns True if key was created
        success = etcd.put_if_not_exists(LEADER_KEY, SCHEDULER_CONSUMER, lease=lease)
        
        if success:
            return True, lease
            
        # Optional: Check if we are already the leader (e.g. restart)
        val, meta = etcd.get(LEADER_KEY)
        if val and val.decode('utf-8') == SCHEDULER_CONSUMER:
            print("Re-acquired own leadership")
            return True, lease
            
        return False, None
    except Exception as e:
        print(f"Etcd connection error: {e}")
        raise e

async def run_scheduler_loop():
    r = redis.from_url(REDIS_URL)
    
    # Create Consumer Group
    try:
        await r.xgroup_create(JOBS_STREAM, SCHEDULER_GROUP, mkstream=True)
        print(f"Created consumer group {SCHEDULER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group {SCHEDULER_GROUP} already exists")
        else:
             # If other error, maybe Redis isn't ready, let the loop handle it
             print(f"Redis Group Error: {e}")

    print("Scheduler loop active processing jobs...")
    
    while True:
        try:
            # 1. Read pending jobs from Stream
            streams = await r.xreadgroup(
                SCHEDULER_GROUP, 
                SCHEDULER_CONSUMER, 
                {JOBS_STREAM: ">"}, 
                count=1, 
                block=2000
            )

            if not streams:
                # Yield control
                await asyncio.sleep(0.1)
                continue

            for stream, messages in streams:
                for message_id, data in messages:
                    job_id = data.get(b"job_id", b"").decode("utf-8")
                    if not job_id:
                        await r.xack(JOBS_STREAM, SCHEDULER_GROUP, message_id)
                        continue

                    print(f"Processing job {job_id}...")
                    
                    # 2. Find a worker
                    workers = await r.smembers(WORKERS_SET)
                    if not workers:
                        print("No workers available! waiting...")
                        await asyncio.sleep(2)
                        continue
                    
                    # Validate workers (Health Check)
                    valid_workers = []
                    for w_bytes in workers:
                         w_id = w_bytes.decode('utf-8')
                         if await r.exists(f"worker:heartbeat:{w_id}"):
                             valid_workers.append(w_id)
                         else:
                             # Lazy cleanup
                             print(f"Removing dead worker from set: {w_id}")
                             await r.srem(WORKERS_SET, w_id)
                    
                    if not valid_workers:
                         print("No alive workers available! waiting...")
                         await asyncio.sleep(2)
                         continue

                    # Pick 1st one
                    worker_id = valid_workers[0]
                    
                    # 3. Assign Job in DB
                    if await assign_job(job_id, worker_id):
                        # 4. Push to Worker Queue
                        worker_queue = f"worker_queue:{worker_id}"
                        await r.rpush(worker_queue, job_id)
                        print(f"Assigned job {job_id} to {worker_id}")
                        
                        # 5. Ack
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
    async_session = get_db_session()
    async for session in async_session:
        try:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                return False
            
            # If already matched or processed
            if job.status not in [JobStatus.PENDING]:
                print(f"Job {job_id} is already {job.status}")
                return True 
                
            job.assigned_worker = worker_id
            job.status = JobStatus.QUEUED
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Scheduler stopping...")
