# ruff: noqa: E402
"""Integration tests for generate_predictions DAG task and /graph/predictions/* API.

Prediction synthesizer is mocked (no real Ollama). All DB operations
(prediction_reports insert, get_latest query) run against live Postgres.
"""
from __future__ import annotations

import asyncio
import sys
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
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.api.deps import get_db, get_rate_limiter
from app.core.models import Base, PredictionReportRow
from app.core.security import create_access_token
from app.graph.schemas import (
    ConceptSignal,
    EmergingDirection,
    PredictedConvergence,
    PredictionReport,
    UnexploredGap,
)
from app.main import app

from arxiv_ingestion_dag import generate_predictions  # type: ignore[import]

# ---------------------------------------------------------------------------
# Fixed test data
# ---------------------------------------------------------------------------

_TOPIC = "AI/ML research"

_FAKE_SIGNALS = [
    ConceptSignal(concept_name="attention", centrality_score=0.9, velocity=5.0,
                  acceleration=1.0, trend="accelerating", composite_score=1.0),
    ConceptSignal(concept_name="transformer", centrality_score=0.6, velocity=3.0,
                  acceleration=0.5, trend="accelerating", composite_score=0.7),
]

_FAKE_REPORT = PredictionReport(
    emerging_directions=[
        EmergingDirection(direction=f"D{i}", reasoning="R", confidence="high")
        for i in range(3)
    ],
    underexplored_gaps=[
        UnexploredGap(gap=f"G{i}", reasoning="R") for i in range(3)
    ],
    predicted_convergences=[
        PredictedConvergence(concept_a="A", concept_b="B", reasoning="R"),
        PredictedConvergence(concept_a="C", concept_b="D", reasoning="R2"),
    ],
    time_horizon_months=12,
    overall_confidence="high",
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
def prediction_db(_loop):
    """Postgres container with schema; patches AsyncSessionLocal for DAG and API."""
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
                # velocity_trend_enum needed by VelocityScore table (referenced in Base.metadata)
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

def _run_dag_task(loop) -> None:
    mock_ti = MagicMock()

    with (
        patch(
            "app.graph.graph_analyzer.GraphAnalyzer.analyze",
            new_callable=AsyncMock,
            return_value=_FAKE_SIGNALS,
        ),
        patch(
            "app.graph.graph_analyzer.GraphAnalyzer.read_signals",
            new_callable=AsyncMock,
            return_value=_FAKE_SIGNALS,
        ),
        patch(
            "app.graph.prediction_synthesizer.PredictionSynthesizer.synthesize",
            new_callable=AsyncMock,
            return_value=_FAKE_REPORT,
        ),
        patch(
            "app.services.rag.get_context_for_text",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        generate_predictions(ti=mock_ti)


def _fetch_reports(loop, sf):
    async def _run():
        async with sf() as session:
            rows = (
                await session.execute(select(PredictionReportRow))
            ).scalars().all()
            return rows

    return loop.run_until_complete(_run())


# ---------------------------------------------------------------------------
# DAG task integration tests
# ---------------------------------------------------------------------------

def test_dag_task_writes_prediction_report_row(prediction_db) -> None:
    loop, sf, _ = prediction_db

    _run_dag_task(loop)

    rows = _fetch_reports(loop, sf)
    assert len(rows) >= 1


def test_dag_task_report_has_correct_jsonb_content(prediction_db) -> None:
    loop, sf, _ = prediction_db

    rows = _fetch_reports(loop, sf)
    row = rows[-1]  # latest

    assert row.topic_context == _TOPIC
    assert row.model_name == "qwen3.5:27b"
    assert row.is_validated is False
    assert "emerging_directions" in row.report
    assert len(row.signals_snapshot) == 2


def test_dag_task_signals_snapshot_has_correct_concepts(prediction_db) -> None:
    loop, sf, _ = prediction_db

    rows = _fetch_reports(loop, sf)
    snapshot = rows[-1].signals_snapshot
    names = {s["concept_name"] for s in snapshot}
    assert "attention" in names
    assert "transformer" in names


def test_dag_task_idempotent_creates_new_row_each_run(prediction_db) -> None:
    """Each run creates a new row (not idempotent by design — archive grows)."""
    loop, sf, _ = prediction_db

    before = len(_fetch_reports(loop, sf))
    _run_dag_task(loop)
    after = len(_fetch_reports(loop, sf))

    assert after == before + 1


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

class _AlwaysAllow:
    async def is_allowed(self, _: str) -> bool:
        return True


@pytest.fixture(scope="module")
def api_client(prediction_db):
    """HTTP test client wired to the prediction_db session factory."""
    loop, sf, _ = prediction_db

    async def _get_db():
        async with sf() as session:
            yield session

    async def _get_rl():
        return _AlwaysAllow()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_rate_limiter] = _get_rl

    token = create_access_token({"sub": "test-user"})
    headers = {"Authorization": f"Bearer {token}"}

    yield loop, headers

    app.dependency_overrides.clear()


def test_get_latest_predictions_returns_200(api_client) -> None:
    loop, headers = api_client

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/graph/predictions/latest",
                params={"topic_context": _TOPIC},
                headers=headers,
            )
        return resp

    resp = loop.run_until_complete(_run())
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "report" in data[0]


def test_get_latest_predictions_requires_auth(api_client) -> None:
    loop, _ = api_client

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/graph/predictions/latest")

    resp = loop.run_until_complete(_run())
    assert resp.status_code == 401


def test_post_generate_prediction_returns_200(api_client) -> None:
    loop, headers = api_client

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with (
                patch(
                    "app.graph.graph_analyzer.GraphAnalyzer.analyze",
                    new_callable=AsyncMock,
                    return_value=_FAKE_SIGNALS,
                ),
                patch(
                    "app.graph.prediction_synthesizer.PredictionSynthesizer.synthesize",
                    new_callable=AsyncMock,
                    return_value=_FAKE_REPORT,
                ),
                patch(
                    "app.api.routers.graph.rag.get_context_for_text",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                resp = await client.post(
                    "/graph/predictions/generate",
                    json={"topic_context": _TOPIC},
                    headers=headers,
                )
        return resp

    resp = loop.run_until_complete(_run())
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "report" in data
    assert data["report"]["overall_confidence"] == "high"


def test_post_generate_requires_auth(api_client) -> None:
    loop, _ = api_client

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/graph/predictions/generate",
                json={"topic_context": _TOPIC},
            )

    resp = loop.run_until_complete(_run())
    assert resp.status_code == 401
