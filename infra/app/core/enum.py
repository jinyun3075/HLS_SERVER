from enum import Enum

class VideoStatus(Enum):
    UPLOADED = "uploaded"
    ENCODING = 'encoding'
    READY = "ready"
    VALIDATION_FAILED = "validation_failed"
    ENCODING_FAILED = "encoding_failed"
    FAILED = "failed"

class JobStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    ENCODING = 'encoding'

class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OVERLOAD = "overload"
    NORMAL = "normal"