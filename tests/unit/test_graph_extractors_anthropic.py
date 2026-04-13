"""Unit tests for AnthropicHaikuExtractor."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import anthropic
from anthropic.types import TextBlock

from app.core.models import Paper
from app.graph.extractors.anthropic_haiku import AnthropicHaikuExtractor


# ---------------------------------------------------------------------------
# Paper factory
# ---------------------------------------------------------------------------

def _paper(arxiv_id: str = "2401.00001") -> MagicMock:
    p = MagicMock(spec=Paper)
    p.arxiv_id = arxiv_id
    p.title = "Test Paper on Neural Networks"
    p.abstract = "We study neural networks and transformers."
    return p


def _make_extractor() -> AnthropicHaikuExtractor:
    return AnthropicHaikuExtractor(api_key="fake-key", poll_interval=0)


# ---------------------------------------------------------------------------
# _sanitize_id
# ---------------------------------------------------------------------------

def test_sanitize_id_replaces_dots() -> None:
    assert AnthropicHaikuExtractor._sanitize_id("2401.00001") == "2401_00001"


def test_sanitize_id_replaces_slashes() -> None:
    assert AnthropicHaikuExtractor._sanitize_id("cs/0501066") == "cs_0501066"


def test_sanitize_id_truncates_to_64() -> None:
    long_id = "a" * 100
    result = AnthropicHaikuExtractor._sanitize_id(long_id)
    assert len(result) == 64


def test_sanitize_id_mixed() -> None:
    assert AnthropicHaikuExtractor._sanitize_id("2202.00146") == "2202_00146"


# ---------------------------------------------------------------------------
# _client factory
# ---------------------------------------------------------------------------

def test_client_factory_returns_async_anthropic() -> None:
    extractor = _make_extractor()
    client = extractor._client()
    assert isinstance(client, anthropic.AsyncAnthropic)


# ---------------------------------------------------------------------------
# extract() — single paper via Messages API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_success() -> None:
    extractor = _make_extractor()
    paper = _paper()

    raw_json = json.dumps({
        "concepts": ["Neural Networks", "Deep Learning"],
        "methods": ["SGD"],
        "datasets": [],
    })
    text_block = TextBlock(type="text", text=raw_json)
    mock_msg = MagicMock()
    mock_msg.content = [text_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.arxiv_id == "2401.00001"
    assert "Neural Networks" in result.concepts
    assert "SGD" in result.methods


@pytest.mark.asyncio
async def test_extract_api_error_returns_empty() -> None:
    extractor = _make_extractor()
    paper = _paper()

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.APIError(
            "error", httpx.Request("POST", "http://api.anthropic.com"), body=None
        )
    )

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.concepts == []
    assert result.methods == []
    assert result.arxiv_id == "2401.00001"


@pytest.mark.asyncio
async def test_extract_empty_content_returns_empty_parse() -> None:
    """No content blocks → raw = '{}' → all lists empty."""
    extractor = _make_extractor()
    paper = _paper()

    mock_msg = MagicMock()
    mock_msg.content = []  # empty → first = None → raw = "{}"

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.concepts == []


@pytest.mark.asyncio
async def test_extract_non_text_block_uses_empty_json() -> None:
    """Non-TextBlock content block → raw = '{}' → empty results."""
    extractor = _make_extractor()
    paper = _paper()

    non_text_block = MagicMock()
    non_text_block.__class__ = MagicMock  # not TextBlock
    mock_msg = MagicMock()
    mock_msg.content = [non_text_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.concepts == []


# ---------------------------------------------------------------------------
# extract_batch() — batch API
# ---------------------------------------------------------------------------

async def _make_async_iter(items: list):
    """Helper to create an async iterator from a list."""
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_extract_batch_empty_papers() -> None:
    extractor = _make_extractor()

    mock_client = AsyncMock()
    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract_batch([])

    # No API calls for empty list
    assert result == {}
    mock_client.messages.batches.create.assert_not_called()


@pytest.mark.asyncio
async def test_extract_batch_single_paper_success() -> None:
    extractor = _make_extractor()
    paper = _paper("2401.00001")

    # Mock batch create response
    mock_batch = MagicMock()
    mock_batch.id = "batch_abc123"

    # Mock poll response — immediately "ended"
    mock_status = MagicMock()
    mock_status.processing_status = "ended"

    # Mock batch result item
    raw_json = json.dumps({"concepts": ["LLM"], "methods": [], "datasets": []})
    text_block = TextBlock(type="text", text=raw_json)
    mock_item = MagicMock()
    mock_item.custom_id = "2401_00001"
    mock_item.result.type = "succeeded"
    mock_item.result.message.content = [text_block]

    mock_client = AsyncMock()
    mock_client.messages.batches.create = AsyncMock(return_value=mock_batch)
    mock_client.messages.batches.retrieve = AsyncMock(return_value=mock_status)
    # batches.results returns an async iterator
    mock_client.messages.batches.results = AsyncMock(
        return_value=_make_async_iter([mock_item])
    )

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract_batch([paper])

    assert "2401.00001" in result
    assert "LLM" in result["2401.00001"].concepts


@pytest.mark.asyncio
async def test_extract_batch_item_failure_returns_empty() -> None:
    """Batch item with result.type != 'succeeded' → empty result for that paper."""
    extractor = _make_extractor()
    paper = _paper("2401.00002")

    mock_batch = MagicMock()
    mock_batch.id = "batch_fail123"

    mock_status = MagicMock()
    mock_status.processing_status = "ended"

    # Failed item
    mock_item = MagicMock()
    mock_item.custom_id = "2401_00002"
    mock_item.result.type = "errored"

    mock_client = AsyncMock()
    mock_client.messages.batches.create = AsyncMock(return_value=mock_batch)
    mock_client.messages.batches.retrieve = AsyncMock(return_value=mock_status)
    mock_client.messages.batches.results = AsyncMock(
        return_value=_make_async_iter([mock_item])
    )

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract_batch([paper])

    assert "2401.00002" in result
    assert result["2401.00002"].concepts == []


@pytest.mark.asyncio
async def test_extract_batch_polls_until_ended() -> None:
    """Polling retries until status == 'ended'."""
    extractor = _make_extractor()
    paper = _paper("2401.00003")

    mock_batch = MagicMock()
    mock_batch.id = "batch_poll123"

    # First call returns "in_progress", second returns "ended"
    in_progress = MagicMock()
    in_progress.processing_status = "in_progress"
    ended = MagicMock()
    ended.processing_status = "ended"

    mock_item = MagicMock()
    mock_item.custom_id = "2401_00003"
    mock_item.result.type = "succeeded"
    mock_item.result.message.content = [
        TextBlock(type="text", text='{"concepts":[],"methods":[],"datasets":[]}')
    ]

    mock_client = AsyncMock()
    mock_client.messages.batches.create = AsyncMock(return_value=mock_batch)
    mock_client.messages.batches.retrieve = AsyncMock(
        side_effect=[in_progress, ended]
    )
    mock_client.messages.batches.results = AsyncMock(
        return_value=_make_async_iter([mock_item])
    )

    with patch.object(extractor, "_client") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await extractor.extract_batch([paper])

    assert mock_client.messages.batches.retrieve.call_count == 2
    assert "2401.00003" in result
