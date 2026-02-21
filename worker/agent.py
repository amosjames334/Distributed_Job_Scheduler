import asyncio
import redis.asyncio as redis


async def heartbeat_loop(worker_id: str, r: redis.Redis, interval: int = 5):
    """Proves this worker is alive by refreshing a TTL key."""
    while True:
        try:
            await r.set(f"worker:heartbeat:{worker_id}", "alive", ex=15)
            await asyncio.sleep(interval)
        except Exception as e:
            print(f"Heartbeat error: {e}")
            await asyncio.sleep(interval)


async def register_worker(worker_id: str, r: redis.Redis, workers_set: str):
    """Register this worker in the available workers set."""
    await r.sadd(workers_set, worker_id)
    print(f"Registered {worker_id} in {workers_set}")


async def listen_for_jobs(worker_id: str, r: redis.Redis, callback):
    """Listen for job assignments via Redis Pub/Sub."""
    channel = f"worker:{worker_id}:jobs"
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    print(f"Subscribed to {channel} for job assignments...")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                job_id = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                print(f"Received job {job_id}")
                asyncio.create_task(callback(job_id))
    except asyncio.CancelledError:
        await pubsub.unsubscribe(channel)
        raise
    except Exception as e:
        print(f"Error in job listener: {e}")
        await asyncio.sleep(5)
