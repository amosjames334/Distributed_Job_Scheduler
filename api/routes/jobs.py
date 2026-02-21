from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from api.app.database import get_db
from api.app.models import JobStatus
from api.services.postgres_client import create_job, get_job_by_id
from api.services.redis_client import enqueue_job
from api.services.minio_client import upload_script, upload_requirements, upload_manifest
from prometheus_client import Counter

router = APIRouter()

JOB_SUBMISSIONS = Counter("job_submissions_total", "Total number of jobs submitted")


class JobSubmit(BaseModel):
    command: List[str] = []
    image: str = "python:3.11-slim"
    resources: dict = {"cpu": 0.5, "mem_mb": 128}
    script: Optional[str] = None


@router.post("/jobs")
async def submit_job(job_data: JobSubmit, db: AsyncSession = Depends(get_db)):
    """Legacy endpoint: JSON body submission."""
    JOB_SUBMISSIONS.inc()

    job = await create_job(
        db,
        command=job_data.command,
        image_base=job_data.image,
    )

    try:
        await enqueue_job(str(job.id))
    except Exception as e:
        print(f"Failed to push to Redis: {e}")

    return {"job_id": str(job.id), "status": job.status.value}


@router.post("/jobs/upload")
async def upload_job(
    script: UploadFile = File(...),
    requirements: UploadFile = File(None),
    image_base: str = Form("python:3.11-slim"),
    retries: int = Form(3),
    timeout: int = Form(300),
    env: str = Form("{}"),
    db: AsyncSession = Depends(get_db),
):
    """New endpoint: multipart upload with script + requirements."""
    JOB_SUBMISSIONS.inc()

    job_id = uuid.uuid4()

    script_data = await script.read()
    upload_script(str(job_id), script_data)

    req_data = b""
    if requirements:
        req_data = await requirements.read()
    upload_requirements(str(job_id), req_data)

    try:
        env_dict = json.loads(env)
    except json.JSONDecodeError:
        env_dict = {}

    manifest = {
        "image_base": image_base,
        "retries": retries,
        "timeout": timeout,
        "env": env_dict,
    }
    upload_manifest(str(job_id), manifest)

    job = await create_job(
        db,
        job_id=job_id,
        image_base=image_base,
        retries_left=retries,
        timeout_secs=timeout,
    )

    try:
        await enqueue_job(str(job_id))
    except Exception as e:
        print(f"Failed to push to Redis: {e}")

    return {"job_id": str(job_id), "status": "PENDING"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    job = await get_job_by_id(db, job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@router.get("/jobresult/{job_id}")
async def get_job_result(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    job = await get_job_by_id(db, job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": str(job.id),
        "result": job.result,
        "status": job.status.value,
        "exit_code": job.exit_code,
        "error_message": job.error_message,
    }
