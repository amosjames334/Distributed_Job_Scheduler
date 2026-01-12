from fastapi import FastAPI, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
import uuid
import os
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from .database import engine, Base, get_db
from .models import Job, JobStatus
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="Distributed Job Scheduler API")

# Metrics
JOB_SUBMISSIONS = Counter('job_submissions_total', 'Total number of jobs submitted')

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

class JobSubmit(BaseModel):
    command: List[str] = []
    image: str = "python:3.9" # Default to python for script execution
    resources: dict = {"cpu": 0.5, "mem_mb": 128}
    script: Optional[str] = None # Optional script content

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/jobs")
async def submit_job(job_data: JobSubmit, db: AsyncSession = Depends(get_db)):
    JOB_SUBMISSIONS.inc()
    
    # 1. Create Job in DB
    new_job = Job(
        command=job_data.command,
        image=job_data.image,
        status=JobStatus.PENDING,
        script_content=job_data.script
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 2. Push to Redis Stream
    # We use a stream key "jobs_stream"
    try:
        await redis_client.xadd("jobs_stream", {"job_id": str(new_job.id)})
        # Ideally we should update status to QUEUED here, but let's keep it simple for MVP
        # Or we can just consider PENDING as "accepted but not yet scheduled"
    except Exception as e:
        # In a real app we might roll back or mark job as failed to submit
        print(f"Failed to push to Redis: {e}")
        # For MVP, we continue, but this is a consistency risk
    
    return {"job_id": str(new_job.id), "status": new_job.status}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    # Simple get endpoint for status check
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    job = await db.get(Job, job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.to_dict()

@app.get("/jobresult/{job_id}")
async def get_job_result(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    job = await db.get(Job, job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"job_id": str(job.id), "result": job.result, "status": job.status}

