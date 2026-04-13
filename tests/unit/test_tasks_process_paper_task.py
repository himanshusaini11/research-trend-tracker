"""Unit tests for the process_user_paper Celery task body and helper functions."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(job_id: str, paper_id: uuid.UUID) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.paper_id = paper_id
    job.status = "pending"
    job.completed_at = None
    return job


def _make_paper(paper_id: uuid.UUID, user_id: uuid.UUID, upload_path: str = "/tmp/test.pdf") -> MagicMock:
    paper = MagicMock()
    paper.id = paper_id
    paper.user_id = user_id
    paper.upload_path = upload_path
    paper.status = "pending"
    paper.concept_count = 0
    return paper


def _make_db_session(job: MagicMock, paper: MagicMock) -> MagicMock:
    """Build a mock Session where execute().scalar_one() returns job then paper."""
    db = MagicMock()
    call_count = [0]

    def execute_side_effect(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one.return_value = job
        else:
            result.scalar_one.return_value = paper
        return result

    db.execute.side_effect = execute_side_effect
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add_all = MagicMock()
    db.close = MagicMock()
    return db


def _make_engine_and_session(job, paper):
    engine = MagicMock()
    engine.dispose = MagicMock()
    db = _make_db_session(job, paper)

    def fake_get_session():
        return engine, db

    return engine, db, fake_get_session


# ---------------------------------------------------------------------------
# _get_session
# ---------------------------------------------------------------------------

def test_get_session_returns_engine_and_session() -> None:
    from app.tasks.process_paper import _get_session

    mock_engine = MagicMock()
    mock_session = MagicMock()
    mock_sess_factory = MagicMock(return_value=mock_session)

    with (
        patch("app.tasks.process_paper.create_engine", return_value=mock_engine),
        patch("app.tasks.process_paper.sessionmaker", return_value=mock_sess_factory),
    ):
        engine, session = _get_session()

    assert engine is mock_engine
    assert session is mock_session


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------

def test_extract_text_returns_joined_pages() -> None:
    from app.tasks.process_paper import _extract_text

    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "hello world"
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "foo bar"

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page1, mock_page2]))
    mock_doc.close = MagicMock()

    with patch("app.tasks.process_paper.fitz.open", return_value=mock_doc):
        result = _extract_text("/fake/path.pdf")

    assert "hello world" in result
    assert "foo bar" in result
    mock_doc.close.assert_called_once()


# ---------------------------------------------------------------------------
# process_user_paper — success path
# ---------------------------------------------------------------------------

def test_process_user_paper_success() -> None:
    from app.tasks.process_paper import process_user_paper

    job_id = str(uuid.uuid4())
    paper_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = _make_job(job_id, paper_id)
    paper = _make_paper(paper_id, user_id, upload_path="/tmp/fake.pdf")
    engine, db, fake_get_session = _make_engine_and_session(job, paper)

    text = "neural network deep learning transformer attention gradient optimization"

    with (
        patch("app.tasks.process_paper._get_session", fake_get_session),
        patch("app.tasks.process_paper._extract_text", return_value=text),
        patch("app.tasks.process_paper.Path") as mock_path,
    ):
        mock_path.return_value.unlink = MagicMock()
        result = process_user_paper(job_id)

    assert result["status"] == "complete"
    assert result["concepts"] > 0
    assert result["edges"] >= 0

    # Job marked complete, paper marked processed
    assert job.status == "complete"
    assert paper.status == "processed"

    # commit called (at least once for job.status=processing, once for final)
    assert db.commit.call_count >= 2
    db.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_process_user_paper_success_deletes_pdf() -> None:
    from app.tasks.process_paper import process_user_paper

    job_id = str(uuid.uuid4())
    paper_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = _make_job(job_id, paper_id)
    paper = _make_paper(paper_id, user_id, upload_path="/tmp/delete_me.pdf")
    engine, db, fake_get_session = _make_engine_and_session(job, paper)

    text = "machine learning neural network training"

    mock_unlink = MagicMock()

    with (
        patch("app.tasks.process_paper._get_session", fake_get_session),
        patch("app.tasks.process_paper._extract_text", return_value=text),
        patch("app.tasks.process_paper.Path") as mock_path_cls,
    ):
        mock_path_cls.return_value.unlink = mock_unlink
        result = process_user_paper(job_id)

    mock_unlink.assert_called_once_with(missing_ok=True)


def test_process_user_paper_pdf_delete_oserror_logged_not_raised() -> None:
    """OSError on PDF delete is swallowed (logged), task still returns complete."""
    from app.tasks.process_paper import process_user_paper

    job_id = str(uuid.uuid4())
    paper_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = _make_job(job_id, paper_id)
    paper = _make_paper(paper_id, user_id)
    engine, db, fake_get_session = _make_engine_and_session(job, paper)

    text = "deep learning model training data"

    with (
        patch("app.tasks.process_paper._get_session", fake_get_session),
        patch("app.tasks.process_paper._extract_text", return_value=text),
        patch("app.tasks.process_paper.Path") as mock_path_cls,
    ):
        mock_path_cls.return_value.unlink.side_effect = OSError("Permission denied")
        result = process_user_paper(job_id)

    # Task still completes successfully
    assert result["status"] == "complete"


# ---------------------------------------------------------------------------
# process_user_paper — empty text path
# ---------------------------------------------------------------------------

def test_process_user_paper_empty_text_raises_and_marks_failed() -> None:
    """Empty PDF text → ValueError → job and paper marked failed."""
    from app.tasks.process_paper import process_user_paper

    job_id = str(uuid.uuid4())
    paper_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = _make_job(job_id, paper_id)
    paper = _make_paper(paper_id, user_id)
    engine, db, fake_get_session = _make_engine_and_session(job, paper)

    # The task calls db.execute multiple times in exception handler too
    # Reset to allow further calls
    call_count = [0]
    def execute_side_effect(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one.return_value = job
        elif call_count[0] == 2:
            result.scalar_one.return_value = paper
        return result

    db.execute.side_effect = execute_side_effect

    with (
        patch("app.tasks.process_paper._get_session", fake_get_session),
        patch("app.tasks.process_paper._extract_text", return_value="   "),  # blank
        patch("app.tasks.process_paper.Path"),
    ):
        with pytest.raises(ValueError, match="no extractable text"):
            process_user_paper(job_id)

    db.rollback.assert_called()
    db.close.assert_called_once()
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# process_user_paper — DB exception in error handler
# ---------------------------------------------------------------------------

def test_process_user_paper_double_failure_still_closes_session() -> None:
    """Exception in the failure handler is swallowed; session still closed."""
    from app.tasks.process_paper import process_user_paper

    job_id = str(uuid.uuid4())
    paper_id = uuid.uuid4()
    user_id = uuid.uuid4()

    job = _make_job(job_id, paper_id)
    paper = _make_paper(paper_id, user_id)
    engine, db, fake_get_session = _make_engine_and_session(job, paper)

    # Make the second commit (in the except block) fail
    commit_count = [0]
    def commit_side_effect():
        commit_count[0] += 1
        if commit_count[0] == 2:
            raise Exception("DB commit failed")

    db.commit.side_effect = commit_side_effect
    # Also make the execute in the except handler fail so it triggers the inner except
    execute_count = [0]
    def execute_side_effect(stmt):
        execute_count[0] += 1
        result = MagicMock()
        if execute_count[0] == 1:
            result.scalar_one.return_value = job
        elif execute_count[0] == 2:
            result.scalar_one.return_value = paper
        else:
            raise Exception("DB error in handler")
        return result

    db.execute.side_effect = execute_side_effect

    with (
        patch("app.tasks.process_paper._get_session", fake_get_session),
        patch("app.tasks.process_paper._extract_text", return_value="   "),  # blank → error
        patch("app.tasks.process_paper.Path"),
    ):
        with pytest.raises(ValueError):
            process_user_paper(job_id)

    # Session still closed in finally
    db.close.assert_called_once()
    engine.dispose.assert_called_once()
