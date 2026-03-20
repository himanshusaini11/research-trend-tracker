"""Unit tests for SemanticScholarClient — no real network calls."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import IngestionError
from app.ingestion.semantic_scholar import SemanticScholarClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


_VALID_RESPONSE: dict = {
    "paperId": "ss-abc123",
    "year": 2024,
    "authors": [{"authorId": "auth-1", "name": "Alice"}],
    "citations": [{"paperId": "cited-1"}, {"paperId": "cited-2"}],
    "references": [{"paperId": "ref-1"}],
}


def _patched_client(mock_get_side_effect) -> tuple:
    """Return (mock_cls_patch, mock_http_client) preconfigured for the fallback path."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.side_effect = (
        mock_get_side_effect
        if isinstance(mock_get_side_effect, list)
        else [mock_get_side_effect]
    )
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls, mock_http


# ---------------------------------------------------------------------------
# 404 — returns None
# ---------------------------------------------------------------------------

async def test_fetch_paper_data_returns_none_on_404() -> None:
    client = SemanticScholarClient(delay_seconds=0)
    mock_cls, mock_http = _patched_client(_mock_response(404))

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", mock_cls):
        with patch("asyncio.sleep"):
            result = await client.fetch_paper_data("2401.00001")

    assert result is None
    mock_http.get.assert_called_once()


# ---------------------------------------------------------------------------
# 429 — exponential backoff, eventual success
# ---------------------------------------------------------------------------

async def test_fetch_paper_data_retries_on_429_and_succeeds() -> None:
    """Client retries on 429 and returns the result on the third attempt."""
    client = SemanticScholarClient(delay_seconds=0, max_retries=3)
    mock_cls, mock_http = _patched_client([
        _mock_response(429),
        _mock_response(429),
        _mock_response(200, _VALID_RESPONSE),
    ])

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", mock_cls):
        with patch("asyncio.sleep"):
            result = await client.fetch_paper_data("2401.00001")

    assert result is not None
    assert result.semantic_scholar_id == "ss-abc123"
    assert mock_http.get.call_count == 3


async def test_fetch_paper_data_raises_after_max_retries_on_429() -> None:
    """IngestionError is raised when all retry attempts return 429."""
    client = SemanticScholarClient(delay_seconds=0, max_retries=2)
    mock_cls, mock_http = _patched_client([
        _mock_response(429),
        _mock_response(429),
        _mock_response(429),
    ])

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", mock_cls):
        with patch("asyncio.sleep"):
            with pytest.raises(IngestionError, match="after 2 retries"):
                await client.fetch_paper_data("2401.00001")

    assert mock_http.get.call_count == 3  # initial + 2 retries


# ---------------------------------------------------------------------------
# API key header
# ---------------------------------------------------------------------------

async def test_api_key_sent_as_x_api_key_header() -> None:
    client = SemanticScholarClient(api_key="secret-key", delay_seconds=0)
    mock_cls, _ = _patched_client(_mock_response(200, _VALID_RESPONSE))

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", mock_cls):
        with patch("asyncio.sleep"):
            await client.fetch_paper_data("2401.00001")

    mock_cls.assert_called_once_with(headers={"x-api-key": "secret-key"}, timeout=30)


async def test_no_api_key_passes_empty_headers() -> None:
    client = SemanticScholarClient(delay_seconds=0)
    mock_cls, _ = _patched_client(_mock_response(200, _VALID_RESPONSE))

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", mock_cls):
        with patch("asyncio.sleep"):
            await client.fetch_paper_data("2401.00001")

    mock_cls.assert_called_once_with(headers={}, timeout=30)


# ---------------------------------------------------------------------------
# Context manager lifecycle
# ---------------------------------------------------------------------------

async def test_context_manager_stores_and_clears_client() -> None:
    """__aenter__ sets _client; __aexit__ closes it and resets to None."""
    client = SemanticScholarClient(api_key="key", delay_seconds=0)
    assert client._client is None

    mock_http = AsyncMock(spec=httpx.AsyncClient)

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", return_value=mock_http):
        async with client:
            assert client._client is mock_http

        mock_http.aclose.assert_awaited_once()
        assert client._client is None


async def test_context_manager_reuses_single_http_client() -> None:
    """Inside a context manager, fetch_paper_data reuses self._client for every call."""
    client = SemanticScholarClient(delay_seconds=0)

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = _mock_response(200, _VALID_RESPONSE)

    with patch("app.ingestion.semantic_scholar.httpx.AsyncClient", return_value=mock_http):
        with patch("asyncio.sleep"):
            async with client:
                await client.fetch_paper_data("2401.00001")
                await client.fetch_paper_data("2401.00002")

    # AsyncClient instantiated once (context manager entry), not once per call
    assert mock_http.get.call_count == 2
