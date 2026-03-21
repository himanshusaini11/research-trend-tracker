"""Unit tests for the extractor factory and backend classes."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.graph.extractors.factory import get_extractor
from app.graph.extractors.ollama import OllamaExtractor
from app.graph.extractors.anthropic_haiku import AnthropicHaikuExtractor
from app.graph.extractors.anthropic_sonnet import AnthropicSonnetExtractor


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def test_get_extractor_ollama() -> None:
    extractor = get_extractor("ollama")
    assert isinstance(extractor, OllamaExtractor)


def test_get_extractor_anthropic_haiku() -> None:
    with patch("app.graph.extractors.factory.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_batch_poll_interval_seconds = 30
        extractor = get_extractor("anthropic-haiku")
    assert isinstance(extractor, AnthropicHaikuExtractor)
    assert not isinstance(extractor, AnthropicSonnetExtractor)


def test_get_extractor_anthropic_sonnet() -> None:
    with patch("app.graph.extractors.factory.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_batch_poll_interval_seconds = 30
        extractor = get_extractor("anthropic-sonnet")
    assert isinstance(extractor, AnthropicSonnetExtractor)


def test_get_extractor_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Unknown extraction backend"):
        get_extractor("gpt-4o")


def test_get_extractor_anthropic_haiku_missing_key_raises() -> None:
    with patch("app.graph.extractors.factory.settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            get_extractor("anthropic-haiku")


def test_get_extractor_anthropic_sonnet_missing_key_raises() -> None:
    with patch("app.graph.extractors.factory.settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            get_extractor("anthropic-sonnet")


# ---------------------------------------------------------------------------
# OllamaExtractor
# ---------------------------------------------------------------------------

def test_ollama_extractor_model_name() -> None:
    extractor = get_extractor("ollama")
    assert isinstance(extractor, OllamaExtractor)


# ---------------------------------------------------------------------------
# AnthropicHaikuExtractor — model defaults
# ---------------------------------------------------------------------------

def test_anthropic_haiku_default_model() -> None:
    ext = AnthropicHaikuExtractor(api_key="k")
    assert ext._model == "claude-haiku-4-5-20251001"


def test_anthropic_sonnet_default_model() -> None:
    ext = AnthropicSonnetExtractor(api_key="k")
    assert ext._model == "claude-sonnet-4-6"


def test_anthropic_sonnet_is_subclass_of_haiku() -> None:
    assert issubclass(AnthropicSonnetExtractor, AnthropicHaikuExtractor)
