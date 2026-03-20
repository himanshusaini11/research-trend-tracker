"""Unit tests for GraphAnalyzer — mocks BridgeNodeDetector and VelocityTracker."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.graph_analyzer import GraphAnalyzer, _normalize
from app.graph.schemas import BridgeNodeResult, ConceptSignal, VelocityResult


# ---------------------------------------------------------------------------
# _normalize helper
# ---------------------------------------------------------------------------

def test_normalize_empty_returns_empty() -> None:
    assert _normalize([]) == []


def test_normalize_single_value_returns_zero() -> None:
    assert _normalize([5.0]) == [0.0]


def test_normalize_all_same_returns_zeros() -> None:
    assert _normalize([3.0, 3.0, 3.0]) == [0.0, 0.0, 0.0]


def test_normalize_range_correct() -> None:
    result = _normalize([0.0, 0.5, 1.0])
    assert result == pytest.approx([0.0, 0.5, 1.0])


def test_normalize_arbitrary_values() -> None:
    result = _normalize([10.0, 20.0, 30.0])
    assert result == pytest.approx([0.0, 0.5, 1.0])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bridge(name: str, score: float) -> BridgeNodeResult:
    return BridgeNodeResult(
        concept_name=name,
        centrality_score=score,
        graph_node_count=10,
        graph_edge_count=20,
    )


def _velocity(name: str, vel: float, accel: float, trend: str = "stable") -> VelocityResult:
    return VelocityResult(
        concept_name=name,
        velocity=vel,
        acceleration=accel,
        trend=trend,  # type: ignore[arg-type]
        weeks_of_data=4,
    )


def _mock_session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Empty graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_returns_empty_when_no_bridge_nodes() -> None:
    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        result = await analyzer.analyze(_mock_session())

    assert result == []


# ---------------------------------------------------------------------------
# Composite score formula
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_composite_score_formula() -> None:
    """
    Two concepts with known centrality + velocity values.
    centrality: [0.8, 0.4] → normalized: [1.0, 0.0]
    velocity:   [20.0, 10.0] → normalized: [1.0, 0.0]
    composite A = 0.6*1.0 + 0.4*1.0 = 1.0
    composite B = 0.6*0.0 + 0.4*0.0 = 0.0
    """
    bridge_results = [_bridge("concept_a", 0.8), _bridge("concept_b", 0.4)]
    velocity_results = [_velocity("concept_a", 20.0, 2.0), _velocity("concept_b", 10.0, 1.0)]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    assert len(signals) == 2
    top = signals[0]
    assert top.concept_name == "concept_a"
    assert top.composite_score == pytest.approx(1.0)
    bottom = signals[1]
    assert bottom.composite_score == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_composite_score_mixed_signals() -> None:
    """
    centrality: [1.0, 0.0] → normalized: [1.0, 0.0]
    velocity: [0.0, 10.0] → normalized: [0.0, 1.0]
    A composite = 0.6*1.0 + 0.4*0.0 = 0.6
    B composite = 0.6*0.0 + 0.4*1.0 = 0.4
    """
    bridge_results = [_bridge("high_centrality", 1.0), _bridge("high_velocity", 0.0)]
    velocity_results = [_velocity("high_centrality", 0.0, 0.0), _velocity("high_velocity", 10.0, 1.0)]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    assert signals[0].concept_name == "high_centrality"
    assert signals[0].composite_score == pytest.approx(0.6)
    assert signals[1].composite_score == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Normalization edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_all_same_centrality_no_division_error() -> None:
    """All concepts with identical centrality — normalized to 0.0, no ZeroDivisionError."""
    bridge_results = [_bridge("a", 0.5), _bridge("b", 0.5), _bridge("c", 0.5)]
    velocity_results = [_velocity("a", 1.0, 0.0), _velocity("b", 2.0, 0.0), _velocity("c", 3.0, 0.0)]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    assert len(signals) == 3
    # centrality normalized to 0 → composite = 0.4 * norm_velocity only
    for s in signals:
        assert 0.0 <= s.composite_score <= 1.0


# ---------------------------------------------------------------------------
# Sorted by composite_score desc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_results_sorted_by_composite_score_desc() -> None:
    bridge_results = [
        _bridge("low", 0.1),
        _bridge("mid", 0.5),
        _bridge("high", 0.9),
    ]
    velocity_results = [
        _velocity("low", 1.0, 0.0),
        _velocity("mid", 5.0, 0.0),
        _velocity("high", 10.0, 0.0),
    ]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    scores = [s.composite_score for s in signals]
    assert scores == sorted(scores, reverse=True)
    assert signals[0].concept_name == "high"


# ---------------------------------------------------------------------------
# Missing velocity data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_concept_missing_velocity_defaults_to_zero() -> None:
    """If VelocityTracker doesn't return a result for a concept, defaults apply."""
    bridge_results = [_bridge("known", 0.8), _bridge("unknown", 0.4)]
    # velocity only for "known" — "unknown" is absent
    velocity_results = [_velocity("known", 10.0, 1.0)]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    unknown_signal = next(s for s in signals if s.concept_name == "unknown")
    assert unknown_signal.velocity == 0.0
    assert unknown_signal.acceleration == 0.0
    assert unknown_signal.trend == "stable"


# ---------------------------------------------------------------------------
# ConceptSignal fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_signal_fields_populated() -> None:
    bridge_results = [_bridge("attention", 0.7)]
    velocity_results = [_velocity("attention", 5.0, 2.0, "accelerating")]

    with (
        patch(
            "app.graph.graph_analyzer.BridgeNodeDetector.compute",
            new_callable=AsyncMock,
            return_value=bridge_results,
        ),
        patch(
            "app.graph.graph_analyzer.VelocityTracker.compute",
            new_callable=AsyncMock,
            return_value=velocity_results,
        ),
    ):
        analyzer = GraphAnalyzer(top_n=5, k_samples=10)
        signals = await analyzer.analyze(_mock_session())

    s = signals[0]
    assert isinstance(s, ConceptSignal)
    assert s.concept_name == "attention"
    assert s.centrality_score == pytest.approx(0.7)
    assert s.velocity == pytest.approx(5.0)
    assert s.acceleration == pytest.approx(2.0)
    assert s.trend == "accelerating"
