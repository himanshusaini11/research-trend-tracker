"""Celery beat tasks: expired user data cleanup and stale upload removal."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.core.config import settings
from app.core.logger import get_logger
from app.core.models import User, UserConcept, UserGraphEdge, UserJob, UserPaper

log = get_logger(__name__)


def _get_session():
    engine = create_engine(settings.postgres_dsn_sync, pool_pre_ping=True)
    Session = sessionmaker(engine)
    return engine, Session()


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_user_data")
def cleanup_expired_user_data() -> dict:
    """Delete all data for users inactive for more than USER_DATA_EXPIRY_DAYS days."""
    engine, db = _get_session()
    deleted_users = 0
    deleted_files = 0

    try:
        cutoff = datetime.now(UTC) - timedelta(days=settings.user_data_expiry_days)

        expired_users = db.execute(
            select(User.id).where(User.last_login < cutoff)
        ).scalars().all()

        if not expired_users:
            log.info("cleanup_expired_user_data", expired_users=0)
            return {"deleted_users": 0, "deleted_files": 0}

        for user_id in expired_users:
            # Collect file paths before deleting rows
            paths = db.execute(
                select(UserPaper.upload_path).where(UserPaper.user_id == user_id)
            ).scalars().all()

            # Delete in FK-safe order
            db.execute(delete(UserJob).where(UserJob.user_id == user_id))
            db.execute(delete(UserConcept).where(UserConcept.user_id == user_id))
            db.execute(delete(UserGraphEdge).where(UserGraphEdge.user_id == user_id))
            db.execute(delete(UserPaper).where(UserPaper.user_id == user_id))

            # Remove files from volume
            for path in paths:
                if path:
                    try:
                        Path(path).unlink(missing_ok=True)
                        deleted_files += 1
                    except OSError as exc:
                        log.warning("file_delete_failed", path=path, error=str(exc))

            deleted_users += 1

        db.commit()
        log.info(
            "cleanup_expired_user_data",
            deleted_users=deleted_users,
            deleted_files=deleted_files,
        )
        return {"deleted_users": deleted_users, "deleted_files": deleted_files}

    except Exception as exc:
        db.rollback()
        log.error("cleanup_expired_user_data_failed", error=str(exc))
        raise
    finally:
        db.close()
        engine.dispose()


@celery_app.task(name="app.tasks.cleanup.cleanup_stale_uploads")
def cleanup_stale_uploads() -> dict:
    """Delete raw PDFs that are still in 'failed' status after 24 hours."""
    engine, db = _get_session()
    deleted = 0

    try:
        cutoff = datetime.now(UTC) - timedelta(hours=24)

        stale_papers = db.execute(
            select(UserPaper).where(
                UserPaper.status == "failed",
                UserPaper.created_at < cutoff,
            )
        ).scalars().all()

        for paper in stale_papers:
            if paper.upload_path:
                try:
                    Path(paper.upload_path).unlink(missing_ok=True)
                    deleted += 1
                except OSError as exc:
                    log.warning("stale_file_delete_failed", path=paper.upload_path, error=str(exc))
            paper.upload_path = None  # mark as cleaned up

        db.commit()
        log.info("cleanup_stale_uploads", deleted_files=deleted)
        return {"deleted_files": deleted}

    except Exception as exc:
        db.rollback()
        log.error("cleanup_stale_uploads_failed", error=str(exc))
        raise
    finally:
        db.close()
        engine.dispose()
