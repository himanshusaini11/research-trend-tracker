"""Unit tests for app/simulation/consensus.py."""
from __future__ import annotations

import pytest

from app.graph.schemas import AgentOpinion
from app.simulation.consensus import (
    compute_consensus,
    compute_opinion_shift,
    extract_death_valleys,
    verdict_from_consensus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opinion(
    persona: str,
    likelihood: str,
    concerns: list[str] | None = None,
    enablers: list[str] | None = None,
) -> AgentOpinion:
    return AgentOpinion(
        persona=persona,
        direction="test direction",
        adoption_likelihood=likelihood,  # type: ignore[arg-type]
        reasoning="some reasoning",
        key_concerns=concerns or [],
        key_enablers=enablers or [],
        confidence_score=0.8,
    )


# ---------------------------------------------------------------------------
# compute_consensus
# ---------------------------------------------------------------------------

def test_consensus_all_high_is_perfect() -> None:
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "high"),
        _opinion("policy_maker", "high"),
    ]
    assert compute_consensus(opinions) == 1.0


def test_consensus_all_low_is_perfect() -> None:
    opinions = [
        _opinion("researcher", "low"),
        _opinion("venture_capitalist", "low"),
        _opinion("policy_maker", "low"),
    ]
    assert compute_consensus(opinions) == 1.0


def test_consensus_all_medium_is_perfect() -> None:
    opinions = [
        _opinion("researcher", "medium"),
        _opinion("venture_capitalist", "medium"),
        _opinion("policy_maker", "medium"),
    ]
    assert compute_consensus(opinions) == 1.0


def test_consensus_max_divergence_is_zero() -> None:
    """high=1.0, medium=0.5, low=0.0 is maximum variance → score 0.0."""
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "medium"),
        _opinion("policy_maker", "low"),
    ]
    result = compute_consensus(opinions)
    assert result == 0.0


def test_consensus_two_agree_one_differs() -> None:
    """Two high + one medium → partial consensus, between 0 and 1."""
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "high"),
        _opinion("policy_maker", "medium"),
    ]
    result = compute_consensus(opinions)
    assert 0.0 < result < 1.0


def test_consensus_single_opinion_returns_one() -> None:
    assert compute_consensus([_opinion("researcher", "high")]) == 1.0


def test_consensus_empty_list_returns_one() -> None:
    assert compute_consensus([]) == 1.0


def test_consensus_result_is_clamped_to_zero_or_above() -> None:
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "low"),
    ]
    result = compute_consensus(opinions)
    assert result >= 0.0


# ---------------------------------------------------------------------------
# compute_opinion_shift
# ---------------------------------------------------------------------------

def test_opinion_shift_no_change_is_zero() -> None:
    opinions = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "medium"),
    ]
    assert compute_opinion_shift(opinions, opinions) == 0.0


def test_opinion_shift_empty_prev_is_zero() -> None:
    curr = [_opinion("researcher", "high")]
    assert compute_opinion_shift([], curr) == 0.0


def test_opinion_shift_high_to_low_is_one() -> None:
    prev = [_opinion("researcher", "high")]
    curr = [_opinion("researcher", "low")]
    result = compute_opinion_shift(prev, curr)
    assert result == 1.0


def test_opinion_shift_medium_to_high_is_half() -> None:
    prev = [_opinion("researcher", "medium")]
    curr = [_opinion("researcher", "high")]
    result = compute_opinion_shift(prev, curr)
    assert result == 0.5


def test_opinion_shift_no_shared_personas_is_zero() -> None:
    prev = [_opinion("researcher", "high")]
    curr = [_opinion("venture_capitalist", "low")]
    assert compute_opinion_shift(prev, curr) == 0.0


def test_opinion_shift_averaged_across_personas() -> None:
    """researcher: high→low (shift 1.0), vc: medium→medium (shift 0.0) → avg 0.5."""
    prev = [
        _opinion("researcher", "high"),
        _opinion("venture_capitalist", "medium"),
    ]
    curr = [
        _opinion("researcher", "low"),
        _opinion("venture_capitalist", "medium"),
    ]
    assert compute_opinion_shift(prev, curr) == 0.5


# ---------------------------------------------------------------------------
# extract_death_valleys
# ---------------------------------------------------------------------------

def test_death_valleys_shared_concern_extracted() -> None:
    opinions = [
        _opinion("researcher", "low", concerns=["scalability", "cost"]),
        _opinion("venture_capitalist", "medium", concerns=["scalability"]),
    ]
    result = extract_death_valleys(opinions)
    assert "scalability" in result


def test_death_valleys_unique_concern_excluded() -> None:
    opinions = [
        _opinion("researcher", "low", concerns=["scalability"]),
        _opinion("venture_capitalist", "medium", concerns=["cost"]),
    ]
    result = extract_death_valleys(opinions)
    assert result == []


def test_death_valleys_requires_two_or_more_mentions() -> None:
    opinions = [
        _opinion("researcher", "low", concerns=["shared", "unique_a"]),
        _opinion("venture_capitalist", "medium", concerns=["shared", "unique_b"]),
        _opinion("policy_maker", "medium", concerns=["unique_c"]),
    ]
    result = extract_death_valleys(opinions)
    assert result == ["shared"]


def test_death_valleys_empty_opinions() -> None:
    assert extract_death_valleys([]) == []


def test_death_valleys_no_concerns() -> None:
    opinions = [
        _opinion("researcher", "high", concerns=[]),
        _opinion("venture_capitalist", "high", concerns=[]),
    ]
    assert extract_death_valleys(opinions) == []


# ---------------------------------------------------------------------------
# verdict_from_consensus
# ---------------------------------------------------------------------------

def test_verdict_high_consensus_is_likely() -> None:
    assert verdict_from_consensus(0.75) == "likely"
    assert verdict_from_consensus(1.0) == "likely"


def test_verdict_medium_consensus_is_contested() -> None:
    assert verdict_from_consensus(0.45) == "contested"
    assert verdict_from_consensus(0.74) == "contested"


def test_verdict_low_consensus_is_unlikely() -> None:
    assert verdict_from_consensus(0.0) == "unlikely"
    assert verdict_from_consensus(0.44) == "unlikely"


def test_verdict_boundary_exactly_075_is_likely() -> None:
    assert verdict_from_consensus(0.75) == "likely"


def test_verdict_boundary_exactly_045_is_contested() -> None:
    assert verdict_from_consensus(0.45) == "contested"
