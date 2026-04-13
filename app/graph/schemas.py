"""Pydantic schemas for graph entity extraction and relation building."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.services.rag import PaperResult


class EntityExtractionResult(BaseModel):
    """Structured output from the entity extractor for a single paper."""

    arxiv_id: str
    concepts: list[str]
    methods: list[str]
    datasets: list[str]


class BridgeNodeResult(BaseModel):
    """Betweenness-centrality result for a single Concept node."""

    concept_name: str
    centrality_score: float
    graph_node_count: int
    graph_edge_count: int


class VelocityResult(BaseModel):
    """Citation-rate acceleration result for a single concept."""

    concept_name: str
    velocity: float
    acceleration: float
    trend: Literal["accelerating", "decelerating", "stable"]
    weeks_of_data: int


class ConceptSignal(BaseModel):
    """Combined bridge-node + velocity signal for a concept."""

    concept_name: str
    centrality_score: float
    velocity: float
    acceleration: float
    trend: str
    composite_score: float


# ---------------------------------------------------------------------------
# Prediction report schemas
# ---------------------------------------------------------------------------

class EmergingDirection(BaseModel):
    direction: str
    reasoning: str
    confidence: Literal["high", "medium", "low"]


class UnexploredGap(BaseModel):
    gap: str
    reasoning: str


class PredictedConvergence(BaseModel):
    concept_a: str
    concept_b: str
    reasoning: str


class PredictionReport(BaseModel):
    emerging_directions: Annotated[list[EmergingDirection], Field(min_length=3, max_length=3)]
    underexplored_gaps: Annotated[list[UnexploredGap], Field(min_length=3, max_length=3)]
    predicted_convergences: Annotated[list[PredictedConvergence], Field(min_length=2, max_length=2)]
    time_horizon_months: int
    overall_confidence: Literal["high", "medium", "low"]


class ArchivedReport(BaseModel):
    id: uuid.UUID
    topic_context: str
    report: dict[str, Any]
    model_name: str
    generated_at: datetime
    is_validated: bool
    sources: list[PaperResult] = []


# ---------------------------------------------------------------------------
# Simulation / ARIS schemas (v3.0.0)
# ---------------------------------------------------------------------------


class AgentPersona(BaseModel):
    name: str
    role: Literal["researcher", "venture_capitalist", "policy_maker"]
    skepticism: Literal["high", "medium", "low"]
    temperature: float


class AgentOpinion(BaseModel):
    persona: str
    direction: str
    adoption_likelihood: Literal["high", "medium", "low"]
    reasoning: str
    key_concerns: list[str]
    key_enablers: list[str]
    confidence_score: float  # 0.0–1.0


class SimulationRound(BaseModel):
    round_number: int
    opinions: list[AgentOpinion]
    consensus_score: float  # 0.0–1.0
    opinion_shift: float    # avg delta from previous round


class AdoptionReport(BaseModel):
    direction: str
    rounds: list[SimulationRound]
    final_consensus: float
    consensus_reached: bool
    death_valleys: list[str]  # shared concerns across 2+ agents
    adoption_verdict: Literal["likely", "contested", "unlikely"]


class SimulationReport(BaseModel):
    topic_context: str
    prediction_report_id: uuid.UUID | None
    adoption_reports: list[AdoptionReport]
    overall_simulation_confidence: Literal["high", "medium", "low"]
    model_name: str
    generated_at: datetime
    duration_seconds: float


class SimulationRequest(BaseModel):
    topic_context: str = "AI/ML research"
    prediction_report_id: uuid.UUID | None = None
    max_rounds: int = 3
