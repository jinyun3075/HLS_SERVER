from typing import Optional, List, TypeVar, Generic
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.enum import VideoStatus, JobStatus, WorkerStatus

T = TypeVar('T')

class VideoResponse(BaseModel):
    id: UUID
    s3_etag: str
    filename: str
    original_path: str
    hls_path: Optional[str] = None
    status: VideoStatus
    encoding_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: UUID
    video_id: UUID
    worker_id: Optional[str] = None
    status: JobStatus
    progress: int
    error_log: Optional[str] = None  # dict에서 str로 변경
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WorkerResponse(BaseModel):
    id: UUID
    hostname: str
    cpu_usage: int
    memory_usage: int
    status: WorkerStatus
    last_heartbeat: datetime

    class Config:
        from_attributes = True

class ResponsePage(BaseModel, Generic[T]):
    total: int
    page: int
    items: List[T]

class VideoUploadRequest(BaseModel):
    filename: str

class PresignedUrlResponse(BaseModel):
    upload_url: str
    object_key: str
