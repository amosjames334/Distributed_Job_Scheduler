import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from api.app.models import Job, JobStatus


async def create_job(
    db: AsyncSession,
    job_id: uuid.UUID = None,
    command: list = None,
    image_base: str = "python:3.11-slim",
    retries_left: int = 3,
    timeout_secs: int = 300,
) -> Job:
    new_job = Job(
        id=job_id or uuid.uuid4(),
        command=command,
        image_base=image_base,
        retries_left=retries_left,
        timeout_secs=timeout_secs,
        status=JobStatus.PENDING,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    return new_job


async def get_job_by_id(db: AsyncSession, job_id: uuid.UUID) -> Optional[Job]:
    return await db.get(Job, job_id)
