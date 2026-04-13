"""Integration tests for /graph endpoints."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.graph.schemas import ConceptSignal


def _auth() -> dict[str, str]:
    token = create_access_token({"sub": "graph-test-user"})
    return {"Authorization": f"Bearer {token}"}


def _signal(name: str, score: float = 0.5) -> ConceptSignal:
    return ConceptSignal(
        concept_name=name,
        centrality_score=score,
        velocity=10.0,
        acceleration=1.0,
        trend="stable",
        composite_score=score,
    )


# ---------------------------------------------------------------------------
# GET /graph/top-concepts
# ---------------------------------------------------------------------------

async def test_top_concepts_returns_list(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    signals = [_signal("transformers", 0.9), _signal("attention", 0.7)]

    with patch("app.api.routers.graph.GraphAnalyzer") as mock_cls:
        mock_analyzer = MagicMock()
        mock_analyzer.read_signals = AsyncMock(return_value=signals)
        mock_cls.return_value = mock_analyzer

        resp = await test_client.get("/graph/top-concepts", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["concept_name"] == "transformers"


async def test_top_concepts_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/graph/top-concepts")
    assert resp.status_code == 401


async def test_top_concepts_empty_returns_empty_list(
    test_client: AsyncClient
) -> None:
    with patch("app.api.routers.graph.GraphAnalyzer") as mock_cls:
        mock_analyzer = MagicMock()
        mock_analyzer.read_signals = AsyncMock(return_value=[])
        mock_cls.return_value = mock_analyzer

        resp = await test_client.get("/graph/top-concepts", headers=_auth())

    assert resp.status_code == 200
    assert resp.json() == []


async def test_top_concepts_with_date_range_calls_date_range_method(
    test_client: AsyncClient
) -> None:
    signals = [_signal("llm", 0.8)]

    with patch("app.api.routers.graph.GraphAnalyzer") as mock_cls:
        mock_analyzer = MagicMock()
        mock_analyzer.read_signals_for_date_range = AsyncMock(return_value=signals)
        mock_cls.return_value = mock_analyzer

        resp = await test_client.get(
            "/graph/top-concepts?paper_from=2024-01-01&paper_to=2024-06-01",
            headers=_auth(),
        )

    assert resp.status_code == 200
    mock_analyzer.read_signals_for_date_range.assert_awaited_once()


# ---------------------------------------------------------------------------
# GET /graph/concepts (paginated)
# ---------------------------------------------------------------------------

async def test_get_concepts_page_returns_slice(
    test_client: AsyncClient
) -> None:
    signals = [_signal(f"concept_{i}", 1.0 - i * 0.1) for i in range(5)]

    with patch("app.api.routers.graph.GraphAnalyzer") as mock_cls:
        mock_analyzer = MagicMock()
        mock_analyzer.read_signals_page = AsyncMock(return_value=signals[:2])
        mock_cls.return_value = mock_analyzer

        resp = await test_client.get(
            "/graph/concepts?limit=2&offset=0", headers=_auth()
        )

    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_concepts_page_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/graph/concepts")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /graph/stats
# ---------------------------------------------------------------------------

async def test_graph_stats_returns_counts(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    resp = await test_client.get("/graph/stats", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert "papers_processed" in body
    assert "last_run" in body
    assert isinstance(body["papers_processed"], int)


async def test_graph_stats_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/graph/stats")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /graph/predictions/latest
# ---------------------------------------------------------------------------

async def test_get_latest_predictions_empty(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    resp = await test_client.get("/graph/predictions/latest", headers=_auth())
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_latest_predictions_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/graph/predictions/latest")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /graph/predictions/generate
# ---------------------------------------------------------------------------

async def test_generate_prediction_success(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    from app.graph.schemas import (
        PredictionReport, EmergingDirection, UnexploredGap, PredictedConvergence
    )

    mock_report = PredictionReport(
        overall_confidence="medium",
        time_horizon_months=12,
        emerging_directions=[
            EmergingDirection(direction=f"Direction {i}", reasoning="r", confidence="high")
            for i in range(3)
        ],
        underexplored_gaps=[
            UnexploredGap(gap=f"Gap {i}", reasoning="reason")
            for i in range(3)
        ],
        predicted_convergences=[
            PredictedConvergence(concept_a="a", concept_b="b", reasoning="r"),
            PredictedConvergence(concept_a="c", concept_b="d", reasoning="r"),
        ],
    )

    with (
        patch("app.api.routers.graph.GraphAnalyzer") as mock_analyzer_cls,
        patch("app.api.routers.graph.rag.get_context_for_text", new_callable=AsyncMock, return_value=[]),
        patch("app.api.routers.graph.PredictionSynthesizer") as mock_synth_cls,
        patch("app.api.routers.graph.ReportArchive") as mock_archive_cls,
    ):
        mock_analyzer = MagicMock()
        mock_analyzer.read_signals = AsyncMock(return_value=[_signal("transformers")])
        mock_analyzer_cls.return_value = mock_analyzer

        mock_synth = MagicMock()
        mock_synth.synthesize = AsyncMock(return_value=mock_report)
        mock_synth_cls.return_value = mock_synth

        mock_archive = MagicMock()
        mock_archive.save = AsyncMock(return_value="test-report-id")
        mock_archive_cls.return_value = mock_archive

        resp = await test_client.post(
            "/graph/predictions/generate",
            json={"topic_context": "AI research"},
            headers=_auth(),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "report" in body
    assert body["id"] == "test-report-id"


async def test_generate_prediction_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/graph/predictions/generate",
        json={"topic_context": "test"},
    )
    assert resp.status_code == 401
