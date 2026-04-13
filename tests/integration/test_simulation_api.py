"""Integration tests for POST /graph/simulation/run and GET /graph/simulation/results."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import PredictionReportRow, SimulationResultRow
from app.core.security import create_access_token


def _auth() -> dict[str, str]:
    token = create_access_token({"sub": "sim-test-user"})
    return {"Authorization": f"Bearer {token}"}


def _prediction_report_row(topic: str = "AI/ML research") -> PredictionReportRow:
    return PredictionReportRow(
        topic_context=topic,
        signals_snapshot={"signals": []},
        report={
            "overall_confidence": "medium",
            "time_horizon_months": 12,
            "emerging_directions": [],
            "underexplored_gaps": [],
            "predicted_convergences": [],
        },
        model_name="llama3.2",
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


def _simulation_result_row(topic: str = "AI/ML research") -> SimulationResultRow:
    return SimulationResultRow(
        topic_context=topic,
        simulation_config={"max_rounds": 3},
        results={
            "overall_simulation_confidence": "medium",
            "adoption_reports": [],
        },
        model_name="llama3.2",
        generated_at=datetime(2024, 1, 2, tzinfo=UTC),
        duration_seconds=12.5,
    )


# ---------------------------------------------------------------------------
# POST /graph/simulation/run
# ---------------------------------------------------------------------------

async def test_run_simulation_dispatches_task(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Happy path: prediction report exists → task dispatched → job_id returned."""
    report_row = _prediction_report_row()
    test_db.add(report_row)
    await test_db.flush()

    mock_task = MagicMock()
    mock_task.id = "celery-job-abc123"

    # Router does a lazy `from app.tasks.run_simulation import run_simulation_task`
    # — patch at the source so the fresh import picks up the mock.
    with patch("app.tasks.run_simulation.run_simulation_task") as mock_celery:
        mock_celery.delay.return_value = mock_task

        resp = await test_client.post(
            "/graph/simulation/run",
            json={"topic_context": "AI/ML research", "max_rounds": 3},
            headers=_auth(),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"


async def test_run_simulation_no_report_returns_404(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """No matching prediction report → 404."""
    resp = await test_client.post(
        "/graph/simulation/run",
        json={"topic_context": "nonexistent topic xyz", "max_rounds": 2},
        headers=_auth(),
    )
    assert resp.status_code == 404
    assert "No prediction report" in resp.json()["detail"]


async def test_run_simulation_with_explicit_report_id(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Explicit prediction_report_id that exists → task dispatched."""
    report_row = _prediction_report_row("explicit-topic")
    test_db.add(report_row)
    await test_db.flush()

    report_id = str(report_row.id)

    mock_task = MagicMock()
    mock_task.id = "celery-job-explicit"

    with patch("app.tasks.run_simulation.run_simulation_task") as mock_celery:
        mock_celery.delay.return_value = mock_task
        resp = await test_client.post(
            "/graph/simulation/run",
            json={
                "topic_context": "explicit-topic",
                "prediction_report_id": report_id,
                "max_rounds": 1,
            },
            headers=_auth(),
        )

    assert resp.status_code == 200
    assert "job_id" in resp.json()


async def test_run_simulation_explicit_report_id_not_found(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Explicit prediction_report_id that does not exist → 404."""
    missing_id = str(uuid.uuid4())
    resp = await test_client.post(
        "/graph/simulation/run",
        json={"topic_context": "AI/ML research", "prediction_report_id": missing_id},
        headers=_auth(),
    )
    assert resp.status_code == 404
    assert "Prediction report not found" in resp.json()["detail"]


async def test_run_simulation_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/graph/simulation/run",
        json={"topic_context": "AI/ML research"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /graph/simulation/results
# ---------------------------------------------------------------------------

async def test_get_simulation_results_empty(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """No rows yet → empty list."""
    resp = await test_client.get(
        "/graph/simulation/results?topic_context=unknown+topic",
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_simulation_results_returns_matching_rows(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Rows inserted for the queried topic are returned."""
    row = _simulation_result_row("AI/ML research")
    test_db.add(row)
    await test_db.flush()

    resp = await test_client.get(
        "/graph/simulation/results?topic_context=AI%2FML+research",
        headers=_auth(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["topic_context"] == "AI/ML research"
    assert data[0]["model_name"] == "llama3.2"
    assert data[0]["duration_seconds"] == 12.5


async def test_get_simulation_results_filters_by_topic(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Results for a different topic are excluded."""
    test_db.add(_simulation_result_row("quantum computing"))
    test_db.add(_simulation_result_row("AI/ML research"))
    await test_db.flush()

    resp = await test_client.get(
        "/graph/simulation/results?topic_context=quantum+computing",
        headers=_auth(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["topic_context"] == "quantum computing" for r in data)
    assert len(data) == 1


async def test_get_simulation_results_respects_limit(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """limit param caps the number of returned rows."""
    for _ in range(4):
        test_db.add(_simulation_result_row("AI/ML research"))
    await test_db.flush()

    resp = await test_client.get(
        "/graph/simulation/results?topic_context=AI%2FML+research&limit=2",
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_simulation_results_response_shape(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    """Every returned object has the expected fields."""
    test_db.add(_simulation_result_row())
    await test_db.flush()

    resp = await test_client.get(
        "/graph/simulation/results",
        headers=_auth(),
    )
    assert resp.status_code == 200
    item = resp.json()[0]
    for field in ("id", "topic_context", "simulation_config", "results",
                  "model_name", "generated_at", "duration_seconds"):
        assert field in item, f"missing field: {field}"


async def test_get_simulation_results_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/graph/simulation/results")
    assert resp.status_code == 401
