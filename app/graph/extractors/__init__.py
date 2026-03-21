"""Pluggable LLM extraction backends for the graph pipeline."""
from app.graph.extractors.base import BaseEntityExtractor
from app.graph.extractors.factory import get_extractor

__all__ = ["BaseEntityExtractor", "get_extractor"]
