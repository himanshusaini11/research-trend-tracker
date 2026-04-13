"""Unit tests for app/simulation/engine.py (nodes + router, no LLM I/O)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.graph.schemas import AgentOpinion, SimulationRound
from app.simulation.engine import (
    SimulationState,
    convergence_router,
    gather_node,
    loop_node,
    scatter_node,
    synthesize_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opinion(
    persona: str = "researcher",
    likelihood: str = "high",
    concerns: list[str] | None = None,
) -> AgentOpinion:
    return AgentOpinion(
        persona=persona,
        direction="emerging direction",
        adoption_likelihood=likelihood,  # type: ignore[arg-type]
        reasoning="test reasoning",
        key_concerns=concerns or [],
        key_enablers=[],
        confidence_score=0.7,
    )


def _base_state(**overrides: object) -> SimulationState:
    state: SimulationState = {
        "direction": "emerging direction",
        "topic_context": "AI/ML research",
        "rag_context": [],
        "current_round": 1,
        "max_rounds": 3,
        "opinions": [],
        "all_rounds": [],
        "consensus_reached": False,
        "final_report": None,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ---------------------------------------------------------------------------
# scatter_node — mocks _call_persona to avoid real HTTP calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scatter_node_returns_valid_opinions() -> None:
    mock_opinion = _opinion("researcher", "high")
    with patch(
        "app.simulation.engine._call_persona",
        new_callable=AsyncMock,
        return_value=mock_opinion,
    ):
        result = await scatter_node(_base_state())
    # 3 personas → 3 opinions
    assert len(result["opinions"]) == 3


@pytest.mark.asyncio
async def test_scatter_node_filters_none_results() -> None:
    """If one persona call fails (returns None), only successful ones are kept."""
    call_count = 0

    async def side_effect(*args, **kwargs):  # noqa: ANN001
        nonlocal call_count
        call_count += 1
        return None if call_count == 1 else _opinion("researcher", "medium")

    with patch("app.simulation.engine._call_persona", side_effect=side_effect):
        result = await scatter_node(_base_state())
    assert len(result["opinions"]) == 2


@pytest.mark.asyncio
async def test_scatter_node_passes_prior_opinions_from_round_2() -> None:
    """Round > 1 should pass existing opinions as prior context."""
    captured_kwargs: list[dict] = []

    async def capture(*args, **kwargs):  # noqa: ANN001
        captured_kwargs.append(kwargs)
        return _opinion()

    prior = [_opinion("researcher", "low")]
    state = _base_state(current_round=2, opinions=prior)
    with patch("app.simulation.engine._call_persona", side_effect=capture):
        await scatter_node(state)

    assert all(kw.get("prior_opinions") == prior for kw in captured_kwargs)


@pytest.mark.asyncio
async def test_scatter_node_no_prior_opinions_in_round_1() -> None:
    """Round 1 should pass empty prior_opinions."""
    captured: list[list] = []

    async def capture(*args, **kwargs):  # noqa: ANN001
        captured.append(kwargs.get("prior_opinions", []))
        return _opinion()

    with patch("app.simulation.engine._call_persona", side_effect=capture):
        await scatter_node(_base_state(current_round=1))

    assert all(p == [] for p in captured)


# ---------------------------------------------------------------------------
# gather_node — pure computation, no mocking needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gather_node_builds_round_record() -> None:
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "high"),
        _opinion("policy_maker", "high"),
    ]
    state = _base_state(opinions=opinions)
    result = await gather_node(state)
    assert len(result["all_rounds"]) == 1
    assert result["all_rounds"][0].round_number == 1


@pytest.mark.asyncio
async def test_gather_node_sets_consensus_reached_when_high() -> None:
    """All-high opinions → consensus 1.0 > 0.8 → consensus_reached True."""
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "high"),
        _opinion("policy_maker", "high"),
    ]
    result = await gather_node(_base_state(opinions=opinions))
    assert result["consensus_reached"] is True


@pytest.mark.asyncio
async def test_gather_node_consensus_not_reached_when_diverged() -> None:
    """Max-divergence opinions → consensus 0.0 ≤ 0.8 → consensus_reached False."""
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "medium"),
        _opinion("policy_maker", "low"),
    ]
    result = await gather_node(_base_state(opinions=opinions))
    assert result["consensus_reached"] is False


@pytest.mark.asyncio
async def test_gather_node_appends_to_existing_rounds() -> None:
    prior_round = SimulationRound(
        round_number=1,
        opinions=[_opinion()],
        consensus_score=0.5,
        opinion_shift=0.0,
    )
    opinions = [_opinion("researcher", "high"), _opinion("venture_capitalist", "high")]
    state = _base_state(current_round=2, opinions=opinions, all_rounds=[prior_round])
    result = await gather_node(state)
    assert len(result["all_rounds"]) == 2


# ---------------------------------------------------------------------------
# convergence_router
# ---------------------------------------------------------------------------

def test_router_returns_synthesize_when_consensus_reached() -> None:
    state = _base_state(consensus_reached=True, current_round=1, max_rounds=3)
    assert convergence_router(state) == "synthesize"


def test_router_returns_synthesize_at_max_rounds() -> None:
    state = _base_state(consensus_reached=False, current_round=3, max_rounds=3)
    assert convergence_router(state) == "synthesize"


def test_router_returns_loop_when_not_converged_and_rounds_remain() -> None:
    state = _base_state(consensus_reached=False, current_round=1, max_rounds=3)
    assert convergence_router(state) == "loop"


def test_router_returns_synthesize_beyond_max_rounds() -> None:
    state = _base_state(consensus_reached=False, current_round=5, max_rounds=3)
    assert convergence_router(state) == "synthesize"


# ---------------------------------------------------------------------------
# loop_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_node_increments_round() -> None:
    state = _base_state(current_round=1)
    result = await loop_node(state)
    assert result["current_round"] == 2


@pytest.mark.asyncio
async def test_loop_node_does_not_mutate_original() -> None:
    state = _base_state(current_round=2)
    result = await loop_node(state)
    assert result is not state
    assert state["current_round"] == 2   # original unchanged


# ---------------------------------------------------------------------------
# synthesize_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_node_produces_adoption_report() -> None:
    opinions = [_opinion("researcher", "high")]
    round_record = SimulationRound(
        round_number=1,
        opinions=opinions,
        consensus_score=1.0,
        opinion_shift=0.0,
    )
    state = _base_state(
        opinions=opinions,
        all_rounds=[round_record],
        consensus_reached=True,
    )
    result = await synthesize_node(state)
    report = result["final_report"]
    assert report is not None
    assert report.direction == "emerging direction"
    assert report.final_consensus == 1.0
    assert report.adoption_verdict == "likely"


@pytest.mark.asyncio
async def test_synthesize_node_collects_death_valleys() -> None:
    """Shared concerns across rounds should appear in death_valleys."""
    opinions = [
        _opinion("researcher", "low", concerns=["fragility", "cost"]),
        _opinion("venture_capitalist", "low", concerns=["fragility"]),
    ]
    round_record = SimulationRound(
        round_number=1,
        opinions=opinions,
        consensus_score=1.0,
        opinion_shift=0.0,
    )
    state = _base_state(opinions=opinions, all_rounds=[round_record])
    result = await synthesize_node(state)
    assert "fragility" in result["final_report"].death_valleys  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_synthesize_node_uses_last_round_consensus() -> None:
    """final_consensus should reflect the last round, not the first."""
    round1 = SimulationRound(
        round_number=1, opinions=[_opinion()], consensus_score=0.2, opinion_shift=0.0
    )
    round2 = SimulationRound(
        round_number=2, opinions=[_opinion()], consensus_score=0.9, opinion_shift=0.5
    )
    state = _base_state(all_rounds=[round1, round2])
    result = await synthesize_node(state)
    assert result["final_report"].final_consensus == 0.9  # type: ignore[union-attr]
