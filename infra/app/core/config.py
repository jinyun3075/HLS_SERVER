import os

class Settings:
    REDIS_URL : str = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
    WORKER_NAME : str = os.environ.get("WORKER_NAME", 'worker_0')

    AWS_ACCESS_KEY: str = os.getenv("AWS_ACCESS_KEY", "test")
    AWS_SECRET_KEY: str = os.getenv("AWS_SECRET_KEY", "test")
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "http://localstack:4566")

    UPLOAD_BUCKET_NAME = 'upload-bucket'
    HLS_BUCKET_NAME = 'hls-bucket'
    REDIS_PREFIX = "s3_file:"

    DB_URL: str = os.getenv("DATABASE_URL", "postgresql://encoder:encoder@db:5432/encoder")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1",
        "http://127.0.0.1:63342",
        "http://localhost:63342",
        "http://cdn-mock"
    ]
