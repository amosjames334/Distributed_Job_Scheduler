import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOBS_STREAM = "jobs:pending"

_client = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL)
    return _client


async def enqueue_job(job_id: str):
    r = get_redis_client()
    await r.xadd(JOBS_STREAM, {"job_id": job_id})
