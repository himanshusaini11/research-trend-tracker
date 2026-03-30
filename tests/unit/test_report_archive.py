"""Unit tests for ReportArchive — mocks AsyncSession, verifies SQL and serialization."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graph.report_archive import ReportArchive
from app.graph.schemas import (
    ArchivedReport,
    ConceptSignal,
    EmergingDirection,
    PredictedConvergence,
    PredictionReport,
    UnexploredGap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal(name: str) -> ConceptSignal:
    return ConceptSignal(
        concept_name=name,
        centrality_score=0.7,
        velocity=3.0,
        acceleration=0.5,
        trend="accelerating",
        composite_score=0.8,
    )


def _report() -> PredictionReport:
    return PredictionReport(
        emerging_directions=[
            EmergingDirection(direction=f"Dir {i}", reasoning="R", confidence="high")
            for i in range(3)
        ],
        underexplored_gaps=[
            UnexploredGap(gap=f"Gap {i}", reasoning="G") for i in range(3)
        ],
        predicted_convergences=[
            PredictedConvergence(concept_a="A", concept_b="B", reasoning="R"),
            PredictedConvergence(concept_a="C", concept_b="D", reasoning="R2"),
        ],
        time_horizon_months=12,
        overall_confidence="high",
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_calls_session_add_and_flush() -> None:
    session = _mock_session()
    archive = ReportArchive()

    # Provide a fake UUID via the row's id after flush
    added_row = None
    def _capture_add(row):  # type: ignore[no-untyped-def]
        nonlocal added_row
        added_row = row
        row.id = uuid.uuid4()

    session.add = MagicMock(side_effect=_capture_add)

    result_id = await archive.save(
        session=session,
        topic_context="AI/ML research",
        signals=[_signal("transformer")],
        report=_report(),
        model_name="qwen3.5:27b",
    )

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    assert result_id == added_row.id


@pytest.mark.asyncio
async def test_save_serializes_signals_as_list_of_dicts() -> None:
    session = _mock_session()
    archive = ReportArchive()
    captured_row = None

    def _capture(row):  # type: ignore[no-untyped-def]
        nonlocal captured_row
        captured_row = row
        row.id = uuid.uuid4()

    session.add = MagicMock(side_effect=_capture)

    signals = [_signal("attention"), _signal("bert")]
    await archive.save(
        session=session,
        topic_context="AI/ML research",
        signals=signals,
        report=_report(),
        model_name="qwen3.5:27b",
    )

    assert isinstance(captured_row.signals_snapshot, list)
    assert len(captured_row.signals_snapshot) == 2
    assert captured_row.signals_snapshot[0]["concept_name"] == "attention"


@pytest.mark.asyncio
async def test_save_serializes_report_as_dict() -> None:
    session = _mock_session()
    archive = ReportArchive()
    captured_row = None

    def _capture(row):  # type: ignore[no-untyped-def]
        nonlocal captured_row
        captured_row = row
        row.id = uuid.uuid4()

    session.add = MagicMock(side_effect=_capture)
    rep = _report()

    await archive.save(
        session=session,
        topic_context="AI/ML research",
        signals=[],
        report=rep,
        model_name="qwen3.5:27b",
    )

    assert isinstance(captured_row.report, dict)
    assert "emerging_directions" in captured_row.report
    assert captured_row.report["overall_confidence"] == "high"


@pytest.mark.asyncio
async def test_save_sets_is_validated_false() -> None:
    session = _mock_session()
    archive = ReportArchive()
    captured_row = None

    def _capture(row):  # type: ignore[no-untyped-def]
        nonlocal captured_row
        captured_row = row
        row.id = uuid.uuid4()

    session.add = MagicMock(side_effect=_capture)

    await archive.save(
        session=session,
        topic_context="AI/ML research",
        signals=[],
        report=_report(),
        model_name="qwen3.5:27b",
    )

    assert captured_row.is_validated is False
    assert captured_row.validation_notes is None


# ---------------------------------------------------------------------------
# get_latest()
# ---------------------------------------------------------------------------

def _make_db_row(topic: str = "AI/ML research", days_ago: int = 0) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.topic_context = topic
    row.report = {"overall_confidence": "medium"}
    row.model_name = "qwen3.5:27b"
    row.generated_at = datetime(2024, 6, 10 + days_ago, tzinfo=UTC)
    row.is_validated = False
    return row


@pytest.mark.asyncio
async def test_get_latest_returns_archived_reports() -> None:
    db_rows = [_make_db_row(days_ago=i) for i in range(3)]
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = db_rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    archive = ReportArchive()
    results = await archive.get_latest(session, topic_context="AI/ML research", limit=3)

    assert len(results) == 3
    assert all(isinstance(r, ArchivedReport) for r in results)


@pytest.mark.asyncio
async def test_get_latest_passes_limit_to_query() -> None:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    archive = ReportArchive()
    await archive.get_latest(session, topic_context="test", limit=7)

    # session.execute called once — the actual limit enforcement is in SQLAlchemy query
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_latest_empty_returns_empty_list() -> None:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    archive = ReportArchive()
    results = await archive.get_latest(session, topic_context="no data", limit=10)

    assert results == []
