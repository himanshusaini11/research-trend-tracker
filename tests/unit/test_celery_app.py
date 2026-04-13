"""Unit tests for app/celery_app.py"""
from __future__ import annotations

from app.celery_app import celery_app


def test_celery_app_name() -> None:
    assert celery_app.main == "rtt"


def test_celery_app_includes_tasks() -> None:
    includes = celery_app.conf.include
    assert "app.tasks.process_paper" in includes
    assert "app.tasks.cleanup" in includes
    assert "app.tasks.embed_papers" in includes


def test_celery_app_serializers() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert "json" in celery_app.conf.accept_content


def test_celery_app_timezone_utc() -> None:
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True


def test_celery_beat_schedule_has_cleanup_tasks() -> None:
    schedule = celery_app.conf.beat_schedule
    task_names = {v["task"] for v in schedule.values()}
    assert "app.tasks.cleanup.cleanup_expired_user_data" in task_names
    assert "app.tasks.cleanup.cleanup_stale_uploads" in task_names


def test_celery_app_reliability_settings() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_track_started is True
