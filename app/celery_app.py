"""Celery application — uses existing Redis instance as broker and result backend."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "rtt",
    broker=settings.redis_dsn,
    backend=settings.redis_dsn,
    include=[
        "app.tasks.process_paper",
        "app.tasks.cleanup",
        "app.tasks.embed_papers",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # ack only after task completes (safer retries)
    worker_prefetch_multiplier=1,  # one task at a time per worker slot
    beat_schedule={
        "cleanup-expired-user-data": {
            "task": "app.tasks.cleanup.cleanup_expired_user_data",
            "schedule": crontab(hour=2, minute=0),  # daily at 2am UTC
        },
        "cleanup-stale-uploads": {
            "task": "app.tasks.cleanup.cleanup_stale_uploads",
            "schedule": crontab(minute=0),  # hourly
        },
    },
)
