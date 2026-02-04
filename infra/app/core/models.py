import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base
from typing import TypeVar
from app.core.enum import VideoStatus, JobStatus, WorkerStatus

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    s3_etag = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(512), nullable=False)
    hls_path = Column(String(512))
    status = Column(SQLEnum(VideoStatus, native_enum=False, length=20), default=VideoStatus.UPLOADED, index=True)
    encoding_json = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class EncodingJob(Base):
    __tablename__ = "encoding_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), index=True)
    worker_id = Column(String(100))
    status = Column(SQLEnum(JobStatus, native_enum=False, length=15), default=JobStatus.PENDING, index=True)
    progress = Column(Integer, default=0)
    error_log = Column(JSONB)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Worker(Base):
    __tablename__ = "workers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname = Column(String(255))
    cpu_usage = Column(Integer, default=0)
    memory_usage = Column(Integer, default=0)
    status = Column(SQLEnum(WorkerStatus, native_enum=False, length=15), default=WorkerStatus.IDLE, index=True)
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

ENTITY_TYPE = TypeVar("ENTITY_TYPE", bound=Base)