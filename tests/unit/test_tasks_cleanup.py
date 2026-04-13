"""Unit tests for app/tasks/cleanup.py — all DB/filesystem calls mocked."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_ctx(session_mock):
    """Return a mock engine and session factory that yield the given session."""
    engine_mock = MagicMock()
    engine_mock.dispose = MagicMock()

    def _fake_get_session():
        return engine_mock, session_mock

    return engine_mock, _fake_get_session


# ---------------------------------------------------------------------------
# cleanup_expired_user_data
# ---------------------------------------------------------------------------

def test_cleanup_expired_user_data_no_expired_users() -> None:
    from app.tasks.cleanup import cleanup_expired_user_data

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        result = cleanup_expired_user_data()

    assert result == {"deleted_users": 0, "deleted_files": 0}
    session.commit.assert_not_called()


def test_cleanup_expired_user_data_deletes_expired_user() -> None:
    from app.tasks.cleanup import cleanup_expired_user_data

    user_id = "user-uuid-1"
    session = MagicMock()

    # First call: expired_users list. Second+ calls: file paths then DELETE stmts
    execute_results = iter([
        MagicMock(**{"scalars.return_value.all.return_value": [user_id]}),
        MagicMock(**{"scalars.return_value.all.return_value": ["/tmp/old_file.pdf"]}),
        MagicMock(),  # delete UserJob
        MagicMock(),  # delete UserConcept
        MagicMock(),  # delete UserGraphEdge
        MagicMock(),  # delete UserPaper
    ])
    session.execute.side_effect = lambda *a, **kw: next(execute_results)

    engine, fake_get = _make_session_ctx(session)

    with (
        patch("app.tasks.cleanup._get_session", fake_get),
        patch("pathlib.Path.unlink") as mock_unlink,
    ):
        result = cleanup_expired_user_data()

    assert result["deleted_users"] == 1
    assert result["deleted_files"] == 1
    session.commit.assert_called_once()


def test_cleanup_expired_user_data_handles_missing_file() -> None:
    """File unlink failure is logged as warning, not raised."""
    from app.tasks.cleanup import cleanup_expired_user_data

    user_id = "user-uuid-2"
    session = MagicMock()
    execute_results = iter([
        MagicMock(**{"scalars.return_value.all.return_value": [user_id]}),
        MagicMock(**{"scalars.return_value.all.return_value": ["/nonexistent/file.pdf"]}),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ])
    session.execute.side_effect = lambda *a, **kw: next(execute_results)
    engine, fake_get = _make_session_ctx(session)

    with (
        patch("app.tasks.cleanup._get_session", fake_get),
        patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")),
    ):
        result = cleanup_expired_user_data()

    # File delete failed, but user is still counted as deleted
    assert result["deleted_users"] == 1
    assert result["deleted_files"] == 0


def test_cleanup_expired_user_data_user_with_no_files() -> None:
    from app.tasks.cleanup import cleanup_expired_user_data

    user_id = "user-uuid-3"
    session = MagicMock()
    execute_results = iter([
        MagicMock(**{"scalars.return_value.all.return_value": [user_id]}),
        MagicMock(**{"scalars.return_value.all.return_value": []}),  # no files
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ])
    session.execute.side_effect = lambda *a, **kw: next(execute_results)
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        result = cleanup_expired_user_data()

    assert result == {"deleted_users": 1, "deleted_files": 0}


def test_cleanup_expired_user_data_db_error_rolls_back() -> None:
    from app.tasks.cleanup import cleanup_expired_user_data

    session = MagicMock()
    session.execute.side_effect = Exception("DB connection lost")
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        with pytest.raises(Exception, match="DB connection lost"):
            cleanup_expired_user_data()

    session.rollback.assert_called_once()
    session.close.assert_called_once()


# ---------------------------------------------------------------------------
# cleanup_stale_uploads
# ---------------------------------------------------------------------------

def _make_stale_paper(path: str | None = "/tmp/stale.pdf") -> MagicMock:
    paper = MagicMock()
    paper.upload_path = path
    return paper


def test_cleanup_stale_uploads_no_stale_papers() -> None:
    from app.tasks.cleanup import cleanup_stale_uploads

    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        result = cleanup_stale_uploads()

    assert result == {"deleted_files": 0}
    session.commit.assert_called_once()


def test_cleanup_stale_uploads_deletes_pdf() -> None:
    from app.tasks.cleanup import cleanup_stale_uploads

    paper = _make_stale_paper("/tmp/old.pdf")
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [paper]
    engine, fake_get = _make_session_ctx(session)

    with (
        patch("app.tasks.cleanup._get_session", fake_get),
        patch("pathlib.Path.unlink") as mock_unlink,
    ):
        result = cleanup_stale_uploads()

    assert result == {"deleted_files": 1}
    assert paper.upload_path is None
    session.commit.assert_called_once()


def test_cleanup_stale_uploads_skips_paper_with_no_path() -> None:
    from app.tasks.cleanup import cleanup_stale_uploads

    paper = _make_stale_paper(None)
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [paper]
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        result = cleanup_stale_uploads()

    assert result == {"deleted_files": 0}


def test_cleanup_stale_uploads_handles_oserror() -> None:
    from app.tasks.cleanup import cleanup_stale_uploads

    paper = _make_stale_paper("/tmp/locked.pdf")
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [paper]
    engine, fake_get = _make_session_ctx(session)

    with (
        patch("app.tasks.cleanup._get_session", fake_get),
        patch("pathlib.Path.unlink", side_effect=OSError("busy")),
    ):
        result = cleanup_stale_uploads()

    # OSError is logged as warning, file counter not incremented
    assert result == {"deleted_files": 0}


def test_cleanup_stale_uploads_db_error_rolls_back() -> None:
    from app.tasks.cleanup import cleanup_stale_uploads

    session = MagicMock()
    session.execute.side_effect = Exception("timeout")
    engine, fake_get = _make_session_ctx(session)

    with patch("app.tasks.cleanup._get_session", fake_get):
        with pytest.raises(Exception, match="timeout"):
            cleanup_stale_uploads()

    session.rollback.assert_called_once()
