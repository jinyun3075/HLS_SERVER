from celery import Celery
from app.core.config import Settings

celery_app = Celery(
    'tasks',
    broker=Settings.REDIS_URL,
    backend=Settings.REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_default_queue='celery',
    worker_prefetch_multiplier=1,
)
