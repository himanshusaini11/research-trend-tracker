"""Unit tests for app/tasks/embed_papers.py — all DB/embedding calls mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest


def _make_engine_session(rows=None, session=None):
    """Return (engine_mock, session_mock, mock_get_sync_engine)."""
    engine_mock = MagicMock()
    session_mock = session or MagicMock()

    if rows is not None:
        session_mock.execute.return_value.fetchall.return_value = rows

    mock_get_engine = MagicMock(return_value=engine_mock)
    return engine_mock, session_mock, mock_get_engine


def _row(paper_id: int, abstract: str):
    """Simulate a SQLAlchemy Row with index access."""
    r = MagicMock()
    r.__getitem__ = lambda self, i: paper_id if i == 0 else abstract
    return r


# ---------------------------------------------------------------------------
# embed_unprocessed_papers
# ---------------------------------------------------------------------------

def test_embed_no_unprocessed_papers() -> None:
    from app.tasks.embed_papers import embed_unprocessed_papers

    engine, session, get_engine = _make_engine_session(rows=[])

    with (
        patch("app.tasks.embed_papers.get_sync_engine", get_engine),
        patch("app.tasks.embed_papers.Session", return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
            )),
            __exit__=MagicMock(return_value=False),
        )),
    ):
        result = embed_unprocessed_papers()

    assert result == {"embedded": 0, "skipped": 0}


def test_embed_single_batch_success() -> None:
    from app.tasks.embed_papers import embed_unprocessed_papers

    rows = [(1, "abstract one"), (2, "abstract two")]
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    # Two Session context managers: first for SELECT, second for INSERT
    select_session = MagicMock()
    select_session.execute.return_value.fetchall.return_value = rows

    insert_session = MagicMock()
    insert_session.execute = MagicMock()
    insert_session.commit = MagicMock()

    sessions = iter([select_session, insert_session])

    class FakeSessionCtx:
        def __init__(self, engine):
            self._session = next(sessions)

        def __enter__(self):
            return self._session

        def __exit__(self, *args):
            return False

    get_engine = MagicMock()

    with (
        patch("app.tasks.embed_papers.get_sync_engine", get_engine),
        patch("app.tasks.embed_papers.Session", FakeSessionCtx),
        patch("app.tasks.embed_papers.asyncio.run", return_value=vectors),
    ):
        result = embed_unprocessed_papers()

    assert result["embedded"] == 2
    assert result["skipped"] == 0
    insert_session.commit.assert_called_once()


def test_embed_partial_failures_skipped() -> None:
    from app.tasks.embed_papers import embed_unprocessed_papers

    rows = [(1, "abstract one"), (2, "abstract two"), (3, "abstract three")]
    # Middle embedding fails (returns None)
    vectors = [[0.1, 0.2], None, [0.7, 0.8]]

    select_session = MagicMock()
    select_session.execute.return_value.fetchall.return_value = rows

    insert_session = MagicMock()
    sessions = iter([select_session, insert_session])

    class FakeSessionCtx:
        def __init__(self, engine):
            self._session = next(sessions)

        def __enter__(self):
            return self._session

        def __exit__(self, *args):
            return False

    with (
        patch("app.tasks.embed_papers.get_sync_engine", MagicMock()),
        patch("app.tasks.embed_papers.Session", FakeSessionCtx),
        patch("app.tasks.embed_papers.asyncio.run", return_value=vectors),
    ):
        result = embed_unprocessed_papers()

    assert result["embedded"] == 2
    assert result["skipped"] == 1


def test_embed_all_fail_returns_zero_embedded() -> None:
    from app.tasks.embed_papers import embed_unprocessed_papers

    rows = [(1, "abstract one"), (2, "abstract two")]
    vectors = [None, None]

    select_session = MagicMock()
    select_session.execute.return_value.fetchall.return_value = rows

    insert_session = MagicMock()
    sessions = iter([select_session, insert_session])

    class FakeSessionCtx:
        def __init__(self, engine):
            self._session = next(sessions)

        def __enter__(self):
            return self._session

        def __exit__(self, *args):
            return False

    with (
        patch("app.tasks.embed_papers.get_sync_engine", MagicMock()),
        patch("app.tasks.embed_papers.Session", FakeSessionCtx),
        patch("app.tasks.embed_papers.asyncio.run", return_value=vectors),
    ):
        result = embed_unprocessed_papers()

    assert result["embedded"] == 0
    assert result["skipped"] == 2
    # No inserts → no commit
    insert_session.commit.assert_not_called()


def test_embed_with_limit_parameter() -> None:
    from app.tasks.embed_papers import embed_unprocessed_papers

    rows = [(1, "abstract")]
    vectors = [[0.1, 0.2]]

    select_session = MagicMock()
    select_session.execute.return_value.fetchall.return_value = rows

    insert_session = MagicMock()
    sessions = iter([select_session, insert_session])

    class FakeSessionCtx:
        def __init__(self, engine):
            self._session = next(sessions)

        def __enter__(self):
            return self._session

        def __exit__(self, *args):
            return False

    with (
        patch("app.tasks.embed_papers.get_sync_engine", MagicMock()),
        patch("app.tasks.embed_papers.Session", FakeSessionCtx),
        patch("app.tasks.embed_papers.asyncio.run", return_value=vectors),
    ):
        result = embed_unprocessed_papers(limit=1)

    assert result["embedded"] == 1
