"""Anthropic Claude Sonnet batch entity extractor.

Higher-quality extraction than Haiku — same Batch API, different model.
Inherits all logic from AnthropicHaikuExtractor; only the model name differs.
"""
from __future__ import annotations

from app.graph.extractors.anthropic_haiku import AnthropicHaikuExtractor


class AnthropicSonnetExtractor(AnthropicHaikuExtractor):
    """Entity extractor backed by Claude Sonnet 4.6 via the Anthropic Batch API."""

    _DEFAULT_MODEL = "claude-sonnet-4-6"
