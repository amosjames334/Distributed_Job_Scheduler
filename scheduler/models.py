from sqlalchemy import Column, String, DateTime, Enum as SAEnum, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime, timezone
import enum
from .database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    PULLING = "PULLING"
    INSTALLING = "INSTALLING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD = "DEAD"
    CANCELED = "CANCELED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    command = Column(JSONB, nullable=True)
    image_base = Column(String, default="python:3.11-slim")
    assigned_worker = Column(String, nullable=True)

    retries_left = Column(Integer, default=3, nullable=False)
    timeout_secs = Column(Integer, default=300, nullable=False)

    exit_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
