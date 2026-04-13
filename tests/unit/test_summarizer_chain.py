"""Unit tests for app/summarizer/chain.py"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import LLMError


def _make_chain(model: str = "llama3.2"):
    from app.summarizer.chain import TrendSummarizerChain
    with patch("app.summarizer.chain.ChatOllama"):
        return TrendSummarizerChain(
            ollama_url="http://localhost:11434",
            model=model,
            timeout=120,
        )


async def test_summarize_success() -> None:
    chain = _make_chain()

    mock_response = MagicMock()
    mock_response.content = "  Transformers dominate NLP research.  "
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(return_value=mock_response)

    result = await chain.summarize("cs.AI", 7, ["transformers", "attention"])

    assert result.summary == "Transformers dominate NLP research."
    assert result.category == "cs.AI"
    assert result.window_days == 7
    assert result.model_used == "llama3.2"
    assert "transformers" in result.keywords_covered
    chain._chain.ainvoke.assert_awaited_once()


async def test_summarize_connect_error_raises_llm_error() -> None:
    chain = _make_chain()
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(LLMError, match="Cannot connect"):
        await chain.summarize("cs.LG", 7, ["neural"])


async def test_summarize_timeout_raises_llm_error() -> None:
    chain = _make_chain()
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    )

    with pytest.raises(LLMError, match="timed out"):
        await chain.summarize("cs.CL", 14, ["bert"])


async def test_summarize_unexpected_error_raises_llm_error() -> None:
    chain = _make_chain()
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(side_effect=RuntimeError("model crashed"))

    with pytest.raises(LLMError, match="Unexpected error"):
        await chain.summarize("stat.ML", 7, ["gp"])


async def test_summarize_keywords_covered_matches_input() -> None:
    chain = _make_chain()
    mock_response = MagicMock()
    mock_response.content = "Summary text."
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(return_value=mock_response)

    keywords = ["diffusion", "score matching", "denoising"]
    result = await chain.summarize("cs.CV", 30, keywords)

    assert result.keywords_covered == keywords


async def test_summarize_generated_at_is_set() -> None:
    chain = _make_chain()
    mock_response = MagicMock()
    mock_response.content = "Some text."
    chain._chain = AsyncMock()
    chain._chain.ainvoke = AsyncMock(return_value=mock_response)

    result = await chain.summarize("cs.AI", 7, ["rl"])

    assert result.generated_at is not None
