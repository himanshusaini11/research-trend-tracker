"""Pydantic schemas for graph entity extraction and relation building."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
