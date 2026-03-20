"""Pydantic schemas for graph entity extraction and relation building."""
from __future__ import annotations

from pydantic import BaseModel


class EntityExtractionResult(BaseModel):
    """Structured output from the entity extractor for a single paper."""

    arxiv_id: str
    concepts: list[str]
    methods: list[str]
    datasets: list[str]
