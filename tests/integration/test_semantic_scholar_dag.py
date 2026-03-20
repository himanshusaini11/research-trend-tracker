# ruff: noqa: E402
"""Integration tests for the fetch_semantic_scholar DAG task.

The task function calls asyncio.run() internally, so these must be *sync*
tests to avoid conflicting with pytest-asyncio's session event loop.
All async setup/verification uses a module-scoped loop managed independently.

Airflow is not installed locally (it runs in Docker). We stub it in
sys.modules and add airflow/dags/ to sys.path so the task function can be
imported without the real Airflow package.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Airflow stub — must happen before any import that touches the DAG file
# ---------------------------------------------------------------------------
for _m in ("airflow", "airflow.operators", "airflow.operators.python"):
    sys.modules.setdefault(_m, MagicMock())

_DAGS_DIR = str(Path(__file__).parent.parent.parent / "airflow" / "dags")
if _DAGS_DIR not in sys.path:
    sys.path.insert(0, _DAGS_DIR)

# ---------------------------------------------------------------------------
# Normal imports (after stubs are in place)
# ---------------------------------------------------------------------------
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.core.models import Base, Paper, PaperAuthor, PaperCitation
from app.ingestion.schemas import (
    SemanticScholarAuthor,
    SemanticScholarPaper,
    SemanticScholarPaperRef,
)

# Import the task function — succeeds now that airflow is stubbed
from arxiv_ingestion_dag import fetch_semantic_scholar  # type: ignore[import]

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_ARXIV_ID_A = "2401.99001"
_ARXIV_ID_B = "2401.99002"
_SS_ID_A = "ss-integration-a"
_SS_ID_B = "ss-integration-b"


def _fake_ss_paper(arxiv_id: str, ss_id: str) -> SemanticScholarPaper:
    return SemanticScholarPaper(
        semantic_scholar_id=ss_id,
        arxiv_id=arxiv_id,
        year=2024,
        authors=[SemanticScholarAuthor(author_id="auth-1", author_name="Alice")],
        citations=[
            SemanticScholarPaperRef(paper_id="cited-1"),
            SemanticScholarPaperRef(paper_id="cited-2"),
        ],
        references=[SemanticScholarPaperRef(paper_id="ref-1")],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _loop():
    """Dedicated event loop for all async work in this module's sync tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def dag_db(_loop):
    """Spin up Postgres, create schema, patch AsyncSessionLocal for the module."""
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url(driver="asyncpg")
        engine = create_async_engine(url, poolclass=NullPool)
        session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        _loop.run_until_complete(_create_schema(engine))

        with patch("app.core.database.AsyncSessionLocal", session_factory):
            yield _loop, session_factory

        _loop.run_until_complete(engine.dispose())


async def _create_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_paper(loop: asyncio.AbstractEventLoop, sf, arxiv_id: str) -> None:
    async def _run() -> None:
        async with sf() as session:
            session.add(Paper(
                arxiv_id=arxiv_id,
                title="Integration Test Paper",
                abstract="Abstract for integration testing.",
                authors=["Alice"],
                categories=["cs.AI"],
                published_at=datetime.now(UTC),
                ingested_at=datetime.now(UTC),
            ))
            await session.commit()

    loop.run_until_complete(_run())


def _run_task(arxiv_ids: list[str], ss_paper: SemanticScholarPaper | None) -> None:
    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = [{"arxiv_id": aid} for aid in arxiv_ids]

    mock_instance = AsyncMock()
    mock_instance.fetch_paper_data.return_value = ss_paper

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.ingestion.semantic_scholar.SemanticScholarClient", return_value=mock_cm):
        fetch_semantic_scholar(ti=mock_ti)


def _count_rows(
    loop: asyncio.AbstractEventLoop,
    sf,
    arxiv_id: str,
) -> tuple[int, int, str | None]:
    async def _run() -> tuple[int, int, str | None]:
        async with sf() as session:
            citations = (
                await session.execute(
                    select(PaperCitation).where(PaperCitation.source_arxiv_id == arxiv_id)
                )
            ).scalars().all()
            authors = (
                await session.execute(
                    select(PaperAuthor).where(PaperAuthor.paper_id == arxiv_id)
                )
            ).scalars().all()
            paper = (
                await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
            ).scalar_one()
            return len(citations), len(authors), paper.semantic_scholar_id

    return loop.run_until_complete(_run())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_task_writes_citations_authors_and_ss_id(dag_db) -> None:
    loop, sf = dag_db
    _seed_paper(loop, sf, _ARXIV_ID_A)
    _run_task([_ARXIV_ID_A], _fake_ss_paper(_ARXIV_ID_A, _SS_ID_A))

    citation_count, author_count, ss_id = _count_rows(loop, sf, _ARXIV_ID_A)

    assert citation_count == 3  # 2 citations + 1 reference
    assert author_count == 1
    assert ss_id == _SS_ID_A


def test_task_stores_correct_citation_types(dag_db) -> None:
    loop, sf = dag_db

    async def _types() -> set[str]:
        async with sf() as session:
            rows = (
                await session.execute(
                    select(PaperCitation).where(PaperCitation.source_arxiv_id == _ARXIV_ID_A)
                )
            ).scalars().all()
            return {r.citation_type for r in rows}

    types = loop.run_until_complete(_types())
    assert types == {"citation", "reference"}


def test_task_idempotent_on_second_run(dag_db) -> None:
    """Running the task twice must not duplicate any rows."""
    loop, sf = dag_db
    _seed_paper(loop, sf, _ARXIV_ID_B)

    ss_paper = _fake_ss_paper(_ARXIV_ID_B, _SS_ID_B)
    _run_task([_ARXIV_ID_B], ss_paper)
    _run_task([_ARXIV_ID_B], ss_paper)

    citation_count, author_count, _ = _count_rows(loop, sf, _ARXIV_ID_B)
    assert citation_count == 3
    assert author_count == 1


def test_task_skips_paper_not_found_in_semantic_scholar(dag_db) -> None:
    """When fetch_paper_data returns None (404), no rows are written."""
    loop, sf = dag_db
    missing_id = "2401.99999"

    _run_task([missing_id], ss_paper=None)

    async def _count() -> tuple[int, int]:
        async with sf() as session:
            citations = (
                await session.execute(
                    select(PaperCitation).where(PaperCitation.source_arxiv_id == missing_id)
                )
            ).scalars().all()
            authors = (
                await session.execute(
                    select(PaperAuthor).where(PaperAuthor.paper_id == missing_id)
                )
            ).scalars().all()
            return len(citations), len(authors)

    citation_count, author_count = loop.run_until_complete(_count())
    assert citation_count == 0
    assert author_count == 0
