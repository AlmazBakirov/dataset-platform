import os
from celery import Celery

BROKER = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "dataset_platform_worker",
    broker=BROKER,
    backend=BACKEND,
    include=["app.worker.jobs"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
)
