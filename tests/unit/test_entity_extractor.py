"""Unit tests for EntityExtractor — mocks Ollama HTTP calls."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.graph.entity_extractor import EntityExtractor
from app.graph.schemas import EntityExtractionResult


def _make_client(response_json: dict) -> MagicMock:
    """Build a mock httpx.AsyncClient whose post() returns a JSON response."""
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = response_json
    resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _extractor() -> EntityExtractor:
    return EntityExtractor(
        ollama_url="http://localhost:11434",
        model="llama3.2",
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Happy-path JSON parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_parses_valid_json() -> None:
    payload = {
        "concepts": ["attention mechanism", "knowledge graph"],
        "methods": ["BERT", "gradient descent"],
        "datasets": ["SQuAD"],
    }
    mock_client = _make_client({"response": json.dumps(payload)})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00001", "Title", "Abstract text")

    assert isinstance(result, EntityExtractionResult)
    assert result.arxiv_id == "2401.00001"
    assert result.concepts == ["attention mechanism", "knowledge graph"]
    assert result.methods == ["BERT", "gradient descent"]
    assert result.datasets == ["SQuAD"]


@pytest.mark.asyncio
async def test_extract_empty_datasets() -> None:
    payload = {"concepts": ["transformer"], "methods": ["fine-tuning"], "datasets": []}
    mock_client = _make_client({"response": json.dumps(payload)})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00002", "T", "A")

    assert result.datasets == []


@pytest.mark.asyncio
async def test_extract_missing_keys_return_empty_lists() -> None:
    """If Ollama omits a key, _coerce_list should return []."""
    payload = {"concepts": ["neural net"]}  # methods and datasets absent
    mock_client = _make_client({"response": json.dumps(payload)})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00003", "T", "A")

    assert result.methods == []
    assert result.datasets == []


@pytest.mark.asyncio
async def test_extract_non_list_value_coerced_to_empty() -> None:
    """If Ollama returns a string instead of a list, coerce to []."""
    payload = {"concepts": "attention", "methods": None, "datasets": []}
    mock_client = _make_client({"response": json.dumps(payload)})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00004", "T", "A")

    assert result.concepts == []
    assert result.methods == []


# ---------------------------------------------------------------------------
# Malformed / missing JSON response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_malformed_json_returns_empty() -> None:
    mock_client = _make_client({"response": "NOT valid JSON {"})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00005", "T", "A")

    assert result.concepts == []
    assert result.methods == []
    assert result.datasets == []


@pytest.mark.asyncio
async def test_extract_empty_response_key_returns_empty() -> None:
    """Ollama returns empty 'response' key — should parse as {}."""
    mock_client = _make_client({"response": "{}"})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00006", "T", "A")

    assert result.concepts == []
    assert result.methods == []


# ---------------------------------------------------------------------------
# HTTP errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_http_error_returns_empty() -> None:
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPError("connection refused")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00007", "T", "A")

    assert result.concepts == []
    assert result.methods == []
    assert result.datasets == []


@pytest.mark.asyncio
async def test_extract_500_raises_for_status_and_returns_empty() -> None:
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=resp,
        )
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        result = await _extractor().extract("2401.00008", "T", "A")

    assert result.concepts == []


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_sends_correct_model_and_format() -> None:
    payload = {"concepts": [], "methods": [], "datasets": []}
    mock_client = _make_client({"response": json.dumps(payload)})

    with patch("app.graph.entity_extractor.httpx.AsyncClient", return_value=mock_client):
        await _extractor().extract("2401.00009", "My Title", "My Abstract")

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert body["model"] == "llama3.2"
    assert body["format"] == "json"
    assert body["stream"] is False
    assert "My Title" in body["prompt"]
    assert "My Abstract" in body["prompt"]
