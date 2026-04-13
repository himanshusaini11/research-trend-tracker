"""Consensus and divergence metrics for simulation rounds."""
from __future__ import annotations

import statistics

from app.graph.schemas import AgentOpinion

_LIKELIHOOD_MAP: dict[str, float] = {"high": 1.0, "medium": 0.5, "low": 0.0}


def _to_float(opinion: AgentOpinion) -> float:
    return _LIKELIHOOD_MAP[opinion.adoption_likelihood]


def compute_consensus(opinions: list[AgentOpinion]) -> float:
    """Return a 0.0–1.0 consensus score based on variance of adoption_likelihood.

    Low variance → high consensus.  Score = 1 - (variance / max_possible_variance).
    Max possible variance is that of {0.0, 0.5, 1.0} = 0.25.
    Returns 1.0 when fewer than 2 opinions are present.
    """
    if len(opinions) < 2:
        return 1.0
    values = [_to_float(o) for o in opinions]
    var = statistics.variance(values)
    max_var = statistics.variance([0.0, 0.5, 1.0])  # 0.25
    return round(max(0.0, 1.0 - (var / max_var)), 4)


def compute_opinion_shift(
    prev_opinions: list[AgentOpinion],
    curr_opinions: list[AgentOpinion],
) -> float:
    """Average absolute delta in adoption_likelihood per persona between rounds."""
    if not prev_opinions:
        return 0.0
    prev_by_persona = {o.persona: _to_float(o) for o in prev_opinions}
    curr_by_persona = {o.persona: _to_float(o) for o in curr_opinions}
    shared = set(prev_by_persona) & set(curr_by_persona)
    if not shared:
        return 0.0
    deltas = [abs(curr_by_persona[p] - prev_by_persona[p]) for p in shared]
    return round(sum(deltas) / len(deltas), 4)


def extract_death_valleys(opinions: list[AgentOpinion]) -> list[str]:
    """Return deduplicated concerns that appear across 2 or more agent opinions."""
    concern_counts: dict[str, int] = {}
    for opinion in opinions:
        for concern in opinion.key_concerns:
            concern_counts[concern] = concern_counts.get(concern, 0) + 1
    return [c for c, count in concern_counts.items() if count >= 2]


def verdict_from_consensus(consensus: float) -> str:
    """Map a consensus score to a human-readable adoption verdict."""
    if consensus >= 0.75:
        return "likely"
    if consensus >= 0.45:
        return "contested"
    return "unlikely"
