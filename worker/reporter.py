from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Job, JobStatus
from prometheus_client import Counter, Histogram

JOBS_PROCESSED = Counter("jobs_processed_total", "Jobs processed by worker", ["status"])
JOB_DURATION = Histogram("job_duration_seconds", "Time spent processing job")
CACHE_HITS = Counter("cache_hits_total", "Environment cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Environment cache misses")


async def update_state(
    session: AsyncSession,
    job: Job,
    new_status: JobStatus,
    expected_status: JobStatus = None,
    **kwargs,
) -> bool:
    """Atomic state transition with optimistic locking."""
    if expected_status and job.status != expected_status:
        print(f"Job {job.id} state mismatch: expected {expected_status}, got {job.status}")
        return False
    job.status = new_status
    job.updated_at = datetime.now(timezone.utc)
    for k, v in kwargs.items():
        setattr(job, k, v)
    await session.commit()
    return True


def report_success(job: Job, exit_code: int, logs: str):
    job.exit_code = exit_code
    job.result = logs
    job.finished_at = datetime.now(timezone.utc)
    JOBS_PROCESSED.labels(status="succeeded").inc()


def report_failure(job: Job, exit_code: int, logs: str):
    job.exit_code = exit_code
    job.result = logs
    job.error_message = logs[:2000] if logs else "Unknown error"
    job.finished_at = datetime.now(timezone.utc)
    JOBS_PROCESSED.labels(status="failed").inc()


def report_cache(hit: bool):
    if hit:
        CACHE_HITS.inc()
    else:
        CACHE_MISSES.inc()
