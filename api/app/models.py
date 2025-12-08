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
    command = Column(JSONB, nullable=False) # List of strings stored as JSON
    image = Column(String, default="ubuntu:latest")
    
    assigned_worker = Column(String, nullable=True)
    
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "status": self.status.value,
            "command": self.command,
            "image": self.image,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
