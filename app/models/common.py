from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class FileDescriptor(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    download_url: Optional[str] = None


class JobMetadata(BaseModel):
    job_id: str
    task_type: str
    status: JobStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    message: Optional[str] = None
    output: Optional[FileDescriptor] = None


class StorageLocation(BaseModel):
    path: Path
    url: Optional[str] = None
