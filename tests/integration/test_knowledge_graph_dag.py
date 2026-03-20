# ruff: noqa: E402
"""Integration tests for the build_knowledge_graph DAG task.

The task calls asyncio.run() internally — tests must be sync to avoid
conflicting with pytest-asyncio's session event loop.

Apache AGE is not available in the testcontainers Postgres image (it requires
a custom-compiled binary). We therefore mock RelationBuilder.setup() and
RelationBuilder._cypher() to no-ops while letting all real DB operations
(paper_authors lookup, paper_citations lookup) execute against a live Postgres.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Airflow stub — must happen before any DAG-file import
# ---------------------------------------------------------------------------
for _m in ("airflow", "airflow.operators", "airflow.operators.python"):
    sys.modules.setdefault(_m, MagicMock())

_DAGS_DIR = str(Path(__file__).parent.parent.parent / "airflow" / "dags")
if _DAGS_DIR not in sys.path:
    sys.path.insert(0, _DAGS_DIR)

# ---------------------------------------------------------------------------
# Normal imports
# ---------------------------------------------------------------------------
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.core.models import Base, Paper, PaperAuthor, PaperCitation
from app.graph.schemas import EntityExtractionResult

from arxiv_ingestion_dag import build_knowledge_graph  # type: ignore[import]

# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

_PAPER_A = "2501.88001"
_PAPER_B = "2501.88002"


def _arxiv_paper_dict(arxiv_id: str, title: str = "Test Paper") -> dict:
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": "An abstract about transformers and knowledge graphs.",
        "published_at": "2024-06-01T00:00:00+00:00",
    }


def _fixed_extraction(arxiv_id: str) -> EntityExtractionResult:
    return EntityExtractionResult(
        arxiv_id=arxiv_id,
        concepts=["knowledge graph", "transformer"],
        methods=["BERT"],
        datasets=[],
    )


# ---------------------------------------------------------------------------
# Module-scoped event loop + DB container
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def graph_dag_db(_loop):
    """Postgres container with schema created; patches AsyncSessionLocal."""
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url(driver="asyncpg")
        engine = create_async_engine(url, poolclass=NullPool)
        sf = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        async def _create():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        _loop.run_until_complete(_create())

        with patch("app.core.database.AsyncSessionLocal", sf):
            yield _loop, sf

        async def _dispose():
            await engine.dispose()

        _loop.run_until_complete(_dispose())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed(loop, sf, arxiv_id: str, authors: list[tuple[str, str]], cites: list[str]) -> None:
    async def _run():
        async with sf() as session:
            session.add(Paper(
                arxiv_id=arxiv_id,
                title="Test Paper",
                abstract="Abstract.",
                authors=[a[1] for a in authors],
                categories=["cs.AI"],
                published_at=datetime.now(UTC),
                ingested_at=datetime.now(UTC),
            ))
            await session.flush()

            for author_id, author_name in authors:
                session.add(PaperAuthor(
                    paper_id=arxiv_id,
                    author_id=author_id,
                    author_name=author_name,
                    fetched_at=datetime.now(UTC),
                ))

            for cited_id in cites:
                session.add(PaperCitation(
                    source_arxiv_id=arxiv_id,
                    cited_paper_id=cited_id,
                    citation_type="citation",
                    fetched_at=datetime.now(UTC),
                ))

            await session.commit()

    loop.run_until_complete(_run())


def _run_task(paper_dicts: list[dict], extraction: EntityExtractionResult | None = None) -> None:
    """Run build_knowledge_graph with AGE calls mocked out."""
    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = paper_dicts

    ext_result = extraction or _fixed_extraction(paper_dicts[0]["arxiv_id"])

    with (
        patch("app.graph.relation_builder.RelationBuilder.setup", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder._cypher", new_callable=AsyncMock),
        patch(
            "app.graph.entity_extractor.EntityExtractor.extract",
            new_callable=AsyncMock,
            return_value=ext_result,
        ),
    ):
        build_knowledge_graph(ti=mock_ti)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_task_processes_paper_and_logs_counts(graph_dag_db) -> None:
    """Task completes without error and processes the seeded paper."""
    loop, sf = graph_dag_db
    _seed(loop, sf, _PAPER_A, [("a1", "Alice"), ("a2", "Bob")], ["cited-x"])

    # Should not raise
    _run_task([_arxiv_paper_dict(_PAPER_A)])


def test_task_calls_build_for_paper_with_correct_authors(graph_dag_db) -> None:
    """build_for_paper receives the authors loaded from the DB."""
    loop, sf = graph_dag_db
    # Paper already seeded in previous test — reuse it

    captured: list[dict] = []

    async def _fake_build(self, *, arxiv_id, title, year, authors, result):
        captured.append({"arxiv_id": arxiv_id, "authors": authors})
        return len(result.concepts) + len(result.methods), len(result.concepts) + len(result.methods)

    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = [_arxiv_paper_dict(_PAPER_A)]

    with (
        patch("app.graph.relation_builder.RelationBuilder.setup", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder._cypher", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder.build_for_paper", _fake_build),
        patch(
            "app.graph.entity_extractor.EntityExtractor.extract",
            new_callable=AsyncMock,
            return_value=_fixed_extraction(_PAPER_A),
        ),
    ):
        build_knowledge_graph(ti=mock_ti)

    assert len(captured) == 1
    assert captured[0]["arxiv_id"] == _PAPER_A
    # Both authors (a1, a2) should be present
    author_ids = {aid for aid, _ in captured[0]["authors"]}
    assert "a1" in author_ids
    assert "a2" in author_ids


def test_task_calls_entity_extractor_for_each_paper(graph_dag_db) -> None:
    """EntityExtractor.extract is called once per paper dict."""
    loop, sf = graph_dag_db
    _seed(loop, sf, _PAPER_B, [("a3", "Carol")], [])

    call_ids: list[str] = []

    async def _fake_extract(self, arxiv_id: str, title: str, abstract: str):
        call_ids.append(arxiv_id)
        return _fixed_extraction(arxiv_id)

    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = [
        _arxiv_paper_dict(_PAPER_A),
        _arxiv_paper_dict(_PAPER_B),
    ]

    with (
        patch("app.graph.relation_builder.RelationBuilder.setup", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder._cypher", new_callable=AsyncMock),
        patch("app.graph.entity_extractor.EntityExtractor.extract", _fake_extract),
    ):
        build_knowledge_graph(ti=mock_ti)

    assert set(call_ids) == {_PAPER_A, _PAPER_B}


def test_task_empty_paper_list_completes_cleanly(graph_dag_db) -> None:
    """Task with no papers in xcom should not raise."""
    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = []

    with (
        patch("app.graph.relation_builder.RelationBuilder.setup", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder._cypher", new_callable=AsyncMock),
    ):
        build_knowledge_graph(ti=mock_ti)  # must not raise


def test_task_year_parsed_from_published_at(graph_dag_db) -> None:
    """Year is correctly parsed from the published_at ISO string."""
    loop, sf = graph_dag_db

    captured_years: list[int | None] = []

    async def _fake_build(self, *, arxiv_id, title, year, authors, result):
        captured_years.append(year)
        return 0, 0

    mock_ti = MagicMock()
    mock_ti.xcom_pull.return_value = [{
        "arxiv_id": _PAPER_A,
        "title": "T",
        "abstract": "A",
        "published_at": "2024-06-15T00:00:00+00:00",
    }]

    with (
        patch("app.graph.relation_builder.RelationBuilder.setup", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder._cypher", new_callable=AsyncMock),
        patch("app.graph.relation_builder.RelationBuilder.build_for_paper", _fake_build),
        patch(
            "app.graph.entity_extractor.EntityExtractor.extract",
            new_callable=AsyncMock,
            return_value=_fixed_extraction(_PAPER_A),
        ),
    ):
        build_knowledge_graph(ti=mock_ti)

    assert captured_years == [2024]
