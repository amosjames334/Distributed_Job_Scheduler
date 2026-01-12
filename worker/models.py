from sqlalchemy import Column, String, DateTime, Enum as SAEnum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime
import enum
from .database import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    command = Column(JSONB, nullable=False)
    image = Column(String, default="ubuntu:latest")
    
    assigned_worker = Column(String, nullable=True)

    script_content = Column(String, nullable=True)
    result = Column(String, nullable=True)
    
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
