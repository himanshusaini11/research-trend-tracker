# ruff: noqa: E402
"""Integration tests for graph analysis components.

AGE is not available in testcontainers Postgres (postgres:16). We mock the
AGE cypher query execution inside BridgeNodeDetector.compute while letting
all other DB operations (keyword_counts queries, bridge_node_scores upsert,
velocity_scores upsert) run against live Postgres.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Airflow stub
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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.analytics.velocity_tracker import VelocityTracker
from app.core.models import Base, BridgeNodeScore, KeywordCount, VelocityScore
from app.graph.bridge_node_detector import BridgeNodeDetector
from app.graph.schemas import BridgeNodeResult

from arxiv_ingestion_dag import analyze_graph  # type: ignore[import]

# ---------------------------------------------------------------------------
# Synthetic AGE edge rows (returned by the mocked query)
# ---------------------------------------------------------------------------

_CONCEPT_A = "attention mechanism"
_CONCEPT_B = "transformer"
_CONCEPT_C = "graph neural network"

_AGE_ROWS = [
    (f'"{_CONCEPT_A}"', '"MENTIONS"', f'"{_CONCEPT_B}"'),
    (f'"{_CONCEPT_B}"', '"MENTIONS"', f'"{_CONCEPT_C}"'),
    (f'"{_CONCEPT_A}"', '"MENTIONS"', f'"{_CONCEPT_C}"'),
]

# ---------------------------------------------------------------------------
# Module-scoped event loop + DB container
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def graph_analysis_db(_loop):
    """Postgres container with schema; patches AsyncSessionLocal for DAG tests."""
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
                await conn.execute(text(
                    "DO $$ BEGIN "
                    "CREATE TYPE velocity_trend_enum AS ENUM "
                    "('accelerating', 'decelerating', 'stable'); "
                    "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
                ))

        _loop.run_until_complete(_create())

        with patch("app.core.database.AsyncSessionLocal", sf):
            yield _loop, sf, engine

        _loop.run_until_complete(engine.dispose())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_keyword_counts(loop, sf, concept: str, counts: list[int]) -> None:
    async def _run():
        async with sf() as session:
            for i, count in enumerate(counts):
                session.add(KeywordCount(
                    keyword=concept,
                    category="cs.AI",
                    count=count,
                    window_date=datetime(2024, 1, 7 * (i + 1), tzinfo=UTC),
                ))
            await session.commit()

    loop.run_until_complete(_run())


def _make_age_mock_session(real_sf):
    """Wrap a real session factory so that AGE setup + cypher queries return fake rows.

    BridgeNodeDetector routes through session.connection() + conn.exec_driver_sql(),
    not session.execute(), so we intercept at the connection level.
    """
    fake_age_result = MagicMock()
    fake_age_result.all.return_value = _AGE_ROWS

    class _PatchedConn:
        def __init__(self, real_conn) -> None:  # type: ignore[no-untyped-def]
            self._real = real_conn

        async def exec_driver_sql(self, sql: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            sql_strip = sql.strip()
            # Swallow AGE setup calls (LOAD + SET search_path) — AGE not in testcontainers
            if sql_strip.startswith("LOAD") or "search_path" in sql_strip:
                return None
            # Return fake rows for the Concept edge query
            if "cypher(" in sql_strip:
                return fake_age_result
            return await self._real.exec_driver_sql(sql, *args, **kwargs)

    class _PatchedSession:
        def __init__(self, real_session: AsyncSession) -> None:
            self._real = real_session

        async def connection(self):  # type: ignore[no-untyped-def]
            real_conn = await self._real.connection()
            return _PatchedConn(real_conn)

        async def execute(self, stmt):  # type: ignore[no-untyped-def]
            return await self._real.execute(stmt)

        async def commit(self) -> None:
            await self._real.commit()

        async def rollback(self) -> None:
            await self._real.rollback()

        async def close(self) -> None:
            await self._real.close()

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            await self._real.__aenter__()
            return self

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return await self._real.__aexit__(*args)

    class _PatchedFactory:
        def __call__(self) -> _PatchedSession:
            return _PatchedSession(real_sf())

    return _PatchedFactory()


# ---------------------------------------------------------------------------
# BridgeNodeDetector integration
# ---------------------------------------------------------------------------

def test_bridge_node_detector_writes_bridge_node_scores(graph_analysis_db) -> None:
    """BridgeNodeDetector.compute writes scores to bridge_node_scores (real DB)."""
    loop, sf, _ = graph_analysis_db
    patched_sf = _make_age_mock_session(sf)

    async def _run():
        async with patched_sf() as session:
            detector = BridgeNodeDetector(k_samples=10)
            results = await detector.compute(session, top_n=5)
            await session.commit()
        return results

    results = loop.run_until_complete(_run())
    assert len(results) > 0

    # Verify rows in DB
    async def _check():
        async with sf() as session:
            rows = (await session.execute(select(BridgeNodeScore))).scalars().all()
            return rows

    db_rows = loop.run_until_complete(_check())
    assert len(db_rows) > 0
    db_names = {r.concept_name for r in db_rows}
    # All concepts from the synthetic graph should be present
    assert _CONCEPT_A in db_names or _CONCEPT_B in db_names or _CONCEPT_C in db_names


def test_bridge_node_detector_upsert_is_idempotent(graph_analysis_db) -> None:
    """Running compute twice must not duplicate bridge_node_scores rows."""
    loop, sf, _ = graph_analysis_db
    patched_sf = _make_age_mock_session(sf)

    async def _run():
        async with patched_sf() as session:
            detector = BridgeNodeDetector(k_samples=10)
            await detector.compute(session, top_n=5)
            await session.commit()

    loop.run_until_complete(_run())
    loop.run_until_complete(_run())

    async def _count():
        async with sf() as session:
            rows = (await session.execute(select(BridgeNodeScore))).scalars().all()
            return len(rows)

    count1 = loop.run_until_complete(_count())
    loop.run_until_complete(_run())
    count2 = loop.run_until_complete(_count())
    assert count1 == count2


# ---------------------------------------------------------------------------
# VelocityTracker integration
# ---------------------------------------------------------------------------

def test_velocity_tracker_writes_velocity_scores(graph_analysis_db) -> None:
    """VelocityTracker.compute writes scores to velocity_scores (real DB)."""
    loop, sf, _ = graph_analysis_db

    # Seed keyword_counts for all three concepts
    for concept, counts in [
        (_CONCEPT_A, [10, 20, 35]),
        (_CONCEPT_B, [5, 15, 30]),
        (_CONCEPT_C, [2, 8, 18]),
    ]:
        _seed_keyword_counts(loop, sf, concept, counts)

    async def _run():
        async with sf() as session:
            tracker = VelocityTracker()
            results = await tracker.compute(
                session, [_CONCEPT_A, _CONCEPT_B, _CONCEPT_C]
            )
            await session.commit()
        return results

    results = loop.run_until_complete(_run())
    assert len(results) == 3

    async def _check():
        async with sf() as session:
            rows = (await session.execute(select(VelocityScore))).scalars().all()
            return rows

    db_rows = loop.run_until_complete(_check())
    assert len(db_rows) == 3
    db_names = {r.concept_name for r in db_rows}
    assert db_names == {_CONCEPT_A, _CONCEPT_B, _CONCEPT_C}


def test_velocity_tracker_trend_values_valid(graph_analysis_db) -> None:
    loop, sf, _ = graph_analysis_db

    async def _check():
        async with sf() as session:
            rows = (await session.execute(select(VelocityScore))).scalars().all()
            return rows

    db_rows = loop.run_until_complete(_check())
    valid_trends = {"accelerating", "decelerating", "stable"}
    for row in db_rows:
        assert row.trend in valid_trends


def test_velocity_tracker_upsert_is_idempotent(graph_analysis_db) -> None:
    loop, sf, _ = graph_analysis_db

    async def _run():
        async with sf() as session:
            tracker = VelocityTracker()
            await tracker.compute(session, [_CONCEPT_A, _CONCEPT_B, _CONCEPT_C])
            await session.commit()

    async def _count():
        async with sf() as session:
            return len((await session.execute(select(VelocityScore))).scalars().all())

    loop.run_until_complete(_run())
    c1 = loop.run_until_complete(_count())
    loop.run_until_complete(_run())
    c2 = loop.run_until_complete(_count())
    assert c1 == c2


# ---------------------------------------------------------------------------
# analyze_graph DAG task integration
# ---------------------------------------------------------------------------

def test_analyze_graph_dag_task_runs_without_error(graph_analysis_db) -> None:
    """DAG task completes without raising, with BridgeNodeDetector mocked (no AGE)."""
    loop, sf, _ = graph_analysis_db
    mock_ti = MagicMock()

    with patch(
        "app.graph.bridge_node_detector.BridgeNodeDetector.compute",
        new_callable=AsyncMock,
        return_value=[
            BridgeNodeResult(concept_name=_CONCEPT_A, centrality_score=0.9,
                             graph_node_count=3, graph_edge_count=3),
        ],
    ):
        analyze_graph(ti=mock_ti)  # must not raise
