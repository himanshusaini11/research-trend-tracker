"""Unit tests for VelocityTracker — mocks TimescaleDB results, verifies math."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analytics.velocity_tracker import VelocityTracker, _classify_trend


# ---------------------------------------------------------------------------
# _classify_trend helper
# ---------------------------------------------------------------------------

def test_classify_trend_accelerating_when_last_two_positive() -> None:
    assert _classify_trend([1.0, 2.0, 3.0]) == "accelerating"


def test_classify_trend_decelerating_when_last_two_negative() -> None:
    assert _classify_trend([-1.0, -2.0, -3.0]) == "decelerating"


def test_classify_trend_stable_when_mixed() -> None:
    assert _classify_trend([2.0, -1.0, 3.0]) == "stable"


def test_classify_trend_stable_with_fewer_than_two_velocities() -> None:
    assert _classify_trend([5.0]) == "stable"


def test_classify_trend_stable_with_empty() -> None:
    assert _classify_trend([]) == "stable"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(weekly_rows: list[tuple]) -> AsyncMock:
    result_mock = MagicMock()
    result_mock.all.return_value = weekly_rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    return session


def _weekly(counts: list[int]) -> list[tuple]:
    """Build fake weekly_rows: (week_date, count)."""
    return [(date(2024, 1, 7 * (i + 1)), c) for i, c in enumerate(counts)]


# ---------------------------------------------------------------------------
# Velocity / acceleration math
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_velocity_correct() -> None:
    # counts: [10, 15, 25] → velocities: [5, 10] → last velocity = 10
    session = _make_session(_weekly([10, 15, 25]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["transformer"])

    assert len(results) == 1
    r = results[0]
    assert r.concept_name == "transformer"
    assert r.velocity == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_compute_acceleration_correct() -> None:
    # counts: [10, 15, 25, 40] → velocities: [5, 10, 15]
    # → accelerations: [5, 5] → last acceleration = 5
    session = _make_session(_weekly([10, 15, 25, 40]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["bert"])

    assert results[0].acceleration == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_compute_trend_accelerating() -> None:
    # counts: [10, 20, 35] → velocities: [10, 15] → both positive → accelerating
    session = _make_session(_weekly([10, 20, 35]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["gnn"])

    assert results[0].trend == "accelerating"


@pytest.mark.asyncio
async def test_compute_trend_decelerating() -> None:
    # counts: [40, 30, 20] → velocities: [-10, -10] → both negative → decelerating
    session = _make_session(_weekly([40, 30, 20]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["rnn"])

    assert results[0].trend == "decelerating"


@pytest.mark.asyncio
async def test_compute_trend_stable_mixed_velocities() -> None:
    # counts: [10, 20, 15] → velocities: [10, -5] → mixed → stable
    session = _make_session(_weekly([10, 20, 15]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["cnn"])

    assert results[0].trend == "stable"


@pytest.mark.asyncio
async def test_compute_weeks_of_data_counted() -> None:
    session = _make_session(_weekly([5, 10, 20, 30]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["attention"])

    assert results[0].weeks_of_data == 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_empty_data_returns_zeros() -> None:
    session = _make_session([])
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["unknown_concept"])

    r = results[0]
    assert r.velocity == 0.0
    assert r.acceleration == 0.0
    assert r.trend == "stable"
    assert r.weeks_of_data == 0


@pytest.mark.asyncio
async def test_compute_single_week_returns_zeros() -> None:
    session = _make_session(_weekly([42]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["solo"])

    r = results[0]
    assert r.velocity == 0.0
    assert r.acceleration == 0.0
    assert r.weeks_of_data == 1


@pytest.mark.asyncio
async def test_compute_two_weeks_zero_acceleration() -> None:
    # Only 2 data points → 1 velocity value → no acceleration possible
    session = _make_session(_weekly([10, 20]))
    tracker = VelocityTracker()
    results = await tracker.compute(session, ["minimal"])

    assert results[0].velocity == pytest.approx(10.0)
    assert results[0].acceleration == 0.0


@pytest.mark.asyncio
async def test_compute_multiple_concepts() -> None:
    call_count = 0

    async def _fake_execute(stmt):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        result_mock = MagicMock()
        result_mock.all.return_value = _weekly([10, 20, 30])
        return result_mock

    session = AsyncMock()
    session.execute = _fake_execute

    tracker = VelocityTracker()
    results = await tracker.compute(session, ["concept_a", "concept_b", "concept_c"])

    assert len(results) == 3
    # One SQL query per concept + 1 upsert = 4 calls
    assert call_count == 4


@pytest.mark.asyncio
async def test_compute_upsert_called() -> None:
    session = _make_session(_weekly([5, 10]))
    tracker = VelocityTracker()
    await tracker.compute(session, ["llm"])

    # execute called for: 1 SQL select + 1 upsert
    assert session.execute.call_count == 2
