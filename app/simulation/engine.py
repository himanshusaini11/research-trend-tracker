"""LangGraph-based multi-agent simulation engine for a single emerging direction."""
from __future__ import annotations

import asyncio
import json
from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.logger import get_logger
from app.graph.schemas import AdoptionReport, AgentOpinion, SimulationRound
from app.services.rag import PaperResult
from app.simulation.consensus import (
    compute_consensus,
    compute_opinion_shift,
    extract_death_valleys,
    verdict_from_consensus,
)
from app.simulation.personas import ALL_PERSONAS, Persona

log = get_logger(__name__)

_OPINION_SCHEMA = """{
  "persona": "<name>",
  "direction": "<direction text>",
  "adoption_likelihood": "high|medium|low",
  "reasoning": "<string>",
  "key_concerns": ["<string>", ...],
  "key_enablers": ["<string>", ...],
  "confidence_score": 0.0
}"""


class SimulationState(TypedDict):
    direction: str
    topic_context: str
    rag_context: list[PaperResult]
    current_round: int
    max_rounds: int
    opinions: list[AgentOpinion]       # opinions from the current round
    all_rounds: list[SimulationRound]  # accumulated round history
    consensus_reached: bool
    final_report: AdoptionReport | None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_opinion_prompt(
    persona: Persona,
    direction: str,
    topic_context: str,
    rag_context: list[PaperResult],
    prior_opinions: list[AgentOpinion],
    round_number: int,
) -> str:
    ctx_block = ""
    if rag_context:
        lines = "\n".join(
            f"[{i + 1}] {p.title} ({p.published_at.date()}): {p.abstract_snippet}"
            for i, p in enumerate(rag_context)
        )
        ctx_block = f"## Relevant Literature\n{lines}\n\n"

    prior_block = ""
    if prior_opinions:
        prior_lines = "\n".join(
            f"- {o.persona}: {o.adoption_likelihood} — {o.reasoning[:120]}"
            for o in prior_opinions
        )
        prior_block = (
            "## Prior Round Positions\n"
            "Other agents assessed this direction as follows. "
            "You may update your view if the evidence warrants it:\n"
            f"{prior_lines}\n\n"
        )

    return (
        f"{ctx_block}{prior_block}"
        f"Round {round_number}. Topic domain: {topic_context}.\n"
        f'Evaluate this emerging research direction: "{direction}"\n\n'
        f"Respond ONLY with valid JSON matching exactly:\n{_OPINION_SCHEMA}"
    )


# ---------------------------------------------------------------------------
# Per-persona LLM call
# ---------------------------------------------------------------------------

async def _call_persona(
    persona: Persona,
    direction: str,
    topic_context: str,
    rag_context: list[PaperResult],
    prior_opinions: list[AgentOpinion],
    round_number: int,
) -> AgentOpinion | None:
    prompt = _build_opinion_prompt(
        persona, direction, topic_context, rag_context, prior_opinions, round_number
    )
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "system": persona.system_prompt,
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "{}")
        data = json.loads(raw)
        data["persona"] = persona.name
        data["direction"] = direction
        return AgentOpinion.model_validate(data)
    except Exception as exc:
        log.warning(
            "simulation_persona_call_failed",
            persona=persona.name,
            round=round_number,
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

async def scatter_node(state: SimulationState) -> SimulationState:
    """Call all personas in parallel for the current round."""
    prior = state["opinions"] if state["current_round"] > 1 else []
    results = await asyncio.gather(
        *[
            _call_persona(
                persona=p,
                direction=state["direction"],
                topic_context=state["topic_context"],
                rag_context=state["rag_context"],
                prior_opinions=prior,
                round_number=state["current_round"],
            )
            for p in ALL_PERSONAS
        ]
    )
    valid: list[AgentOpinion] = [r for r in results if r is not None]
    return {**state, "opinions": valid}


async def gather_node(state: SimulationState) -> SimulationState:
    """Aggregate opinions, compute consensus, record round."""
    opinions = state["opinions"]
    prev_opinions = state["all_rounds"][-1].opinions if state["all_rounds"] else []
    consensus = compute_consensus(opinions)
    shift = compute_opinion_shift(prev_opinions, opinions)
    round_record = SimulationRound(
        round_number=state["current_round"],
        opinions=opinions,
        consensus_score=consensus,
        opinion_shift=shift,
    )
    return {
        **state,
        "all_rounds": [*state["all_rounds"], round_record],
        "consensus_reached": consensus > 0.8,
    }


def convergence_router(state: SimulationState) -> str:
    """Route to 'loop' or 'synthesize'."""
    if state["consensus_reached"] or state["current_round"] >= state["max_rounds"]:
        return "synthesize"
    return "loop"


async def loop_node(state: SimulationState) -> SimulationState:
    """Increment the round counter before the next scatter."""
    return {**state, "current_round": state["current_round"] + 1}


async def synthesize_node(state: SimulationState) -> SimulationState:
    """Build the final AdoptionReport from all rounds."""
    all_opinions = [
        opinion
        for rnd in state["all_rounds"]
        for opinion in rnd.opinions
    ]
    death_valleys = extract_death_valleys(all_opinions)
    final_consensus = state["all_rounds"][-1].consensus_score if state["all_rounds"] else 0.0
    verdict = verdict_from_consensus(final_consensus)

    report = AdoptionReport(
        direction=state["direction"],
        rounds=state["all_rounds"],
        final_consensus=final_consensus,
        consensus_reached=state["consensus_reached"],
        death_valleys=death_valleys,
        adoption_verdict=verdict,
    )
    return {**state, "final_report": report}


# ---------------------------------------------------------------------------
# Graph construction (compiled once at import time)
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g: StateGraph = StateGraph(SimulationState)
    g.add_node("scatter", scatter_node)
    g.add_node("gather", gather_node)
    g.add_node("loop", loop_node)
    g.add_node("synthesize", synthesize_node)

    g.set_entry_point("scatter")
    g.add_edge("scatter", "gather")
    g.add_conditional_edges(
        "gather",
        convergence_router,
        {"loop": "loop", "synthesize": "synthesize"},
    )
    g.add_edge("loop", "scatter")
    g.add_edge("synthesize", END)
    return g


_compiled_graph = _build_graph().compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_direction_simulation(
    direction: str,
    topic_context: str,
    rag_context: list[PaperResult],
    max_rounds: int = 3,
) -> AdoptionReport:
    """Run the full state machine for one emerging direction.

    Raises RuntimeError if the graph exits without producing a report
    (should never happen in practice given synthesize_node always runs last).
    """
    initial_state: SimulationState = {
        "direction": direction,
        "topic_context": topic_context,
        "rag_context": rag_context,
        "current_round": 1,
        "max_rounds": max_rounds,
        "opinions": [],
        "all_rounds": [],
        "consensus_reached": False,
        "final_report": None,
    }
    final_state: SimulationState = await _compiled_graph.ainvoke(initial_state)
    if final_state["final_report"] is None:
        raise RuntimeError(
            f"Simulation produced no report for direction: {direction!r}"
        )
    return final_state["final_report"]
