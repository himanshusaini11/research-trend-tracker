"""Unit tests for graph extractor base class and Ollama extractor."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.models import Paper
from app.graph.extractors.base import BaseEntityExtractor, _coerce_list, build_user_prompt
from app.graph.extractors.ollama import OllamaExtractor
from app.graph.schemas import EntityExtractionResult


# ---------------------------------------------------------------------------
# Paper factory
# ---------------------------------------------------------------------------

def _paper(arxiv_id: str = "2401.00001") -> Paper:
    p = MagicMock(spec=Paper)
    p.arxiv_id = arxiv_id
    p.title = "Test Paper on Neural Networks"
    p.abstract = "We study neural networks and transformers for NLP tasks."
    return p


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def test_build_user_prompt_includes_title_and_abstract() -> None:
    p = _paper()
    prompt = build_user_prompt(p)
    assert "Test Paper on Neural Networks" in prompt
    assert "neural networks" in prompt


def test_build_user_prompt_truncates_abstract() -> None:
    p = _paper()
    p.abstract = "x" * 1000
    prompt = build_user_prompt(p)
    # abstract is truncated to 800 chars
    assert "x" * 800 in prompt
    assert "x" * 801 not in prompt


# ---------------------------------------------------------------------------
# _coerce_list
# ---------------------------------------------------------------------------

def test_coerce_list_returns_list_of_strings() -> None:
    result = _coerce_list(["Neural Networks", "Transformers"])
    assert result == ["Neural Networks", "Transformers"]


def test_coerce_list_non_list_returns_empty() -> None:
    assert _coerce_list("not a list") == []
    assert _coerce_list(None) == []
    assert _coerce_list(42) == []


def test_coerce_list_filters_empty_values() -> None:
    result = _coerce_list(["Valid", "", None, "Also valid"])
    assert "Valid" in result
    assert "Also valid" in result
    assert "" not in result


def test_coerce_list_strips_surrogates() -> None:
    # Surrogate chars (U+D800-U+DFFF) should be stripped
    result = _coerce_list(["\ud83d\ude00valid"])  # surrogate + "valid"
    assert all(r.isascii() or r.isprintable() for r in result)


# ---------------------------------------------------------------------------
# BaseEntityExtractor._parse
# ---------------------------------------------------------------------------

class _ConcreteExtractor(BaseEntityExtractor):
    """Minimal concrete subclass for testing the base class methods."""

    async def extract(self, paper: Paper) -> EntityExtractionResult:
        return self._empty(paper.arxiv_id)

    async def extract_batch(self, papers):
        return {}


def test_parse_valid_json() -> None:
    extractor = _ConcreteExtractor()
    raw = json.dumps({
        "concepts": ["Attention", "Transformers"],
        "methods": ["Self-Attention"],
        "datasets": ["ImageNet"],
    })
    result = extractor._parse("2401.00001", raw)
    assert result.arxiv_id == "2401.00001"
    assert "Attention" in result.concepts
    assert "Self-Attention" in result.methods
    assert "ImageNet" in result.datasets


def test_parse_empty_string_returns_empty() -> None:
    extractor = _ConcreteExtractor()
    result = extractor._parse("2401.00001", "")
    assert result.concepts == []
    assert result.methods == []
    assert result.datasets == []


def test_parse_malformed_json_returns_empty() -> None:
    extractor = _ConcreteExtractor()
    result = extractor._parse("2401.00002", "{not valid json}")
    assert result.concepts == []


def test_parse_markdown_fenced_json() -> None:
    extractor = _ConcreteExtractor()
    raw = '```json\n{"concepts": ["GAN"], "methods": [], "datasets": []}\n```'
    result = extractor._parse("2401.00003", raw)
    assert "GAN" in result.concepts


def test_parse_think_block_stripped() -> None:
    extractor = _ConcreteExtractor()
    raw = '<think>reasoning here</think>{"concepts": ["LLM"], "methods": [], "datasets": []}'
    result = extractor._parse("2401.00004", raw)
    assert "LLM" in result.concepts


def test_parse_missing_keys_returns_empty_lists() -> None:
    extractor = _ConcreteExtractor()
    raw = json.dumps({"concepts": ["X"]})  # missing methods and datasets
    result = extractor._parse("2401.00005", raw)
    assert result.methods == []
    assert result.datasets == []


def test_empty_result() -> None:
    extractor = _ConcreteExtractor()
    result = extractor._empty("2401.99999")
    assert result.arxiv_id == "2401.99999"
    assert result.concepts == []
    assert result.methods == []
    assert result.datasets == []


# ---------------------------------------------------------------------------
# OllamaExtractor.extract
# ---------------------------------------------------------------------------

async def test_ollama_extract_success() -> None:
    extractor = OllamaExtractor(
        ollama_url="http://localhost:11434",
        model="qwen2.5",
        timeout=30,
    )
    paper = _paper()
    raw_json = json.dumps({
        "concepts": ["Neural Networks", "Deep Learning"],
        "methods": ["Backpropagation"],
        "datasets": [],
    })
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": raw_json}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.graph.extractors.ollama.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.arxiv_id == "2401.00001"
    assert "Neural Networks" in result.concepts


async def test_ollama_extract_http_error_returns_empty() -> None:
    extractor = OllamaExtractor("http://localhost:11434", "qwen2.5", 30)
    paper = _paper()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

    with patch("app.graph.extractors.ollama.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await extractor.extract(paper)

    assert result.concepts == []
    assert result.methods == []


async def test_ollama_extract_batch_returns_dict() -> None:
    extractor = OllamaExtractor("http://localhost:11434", "qwen2.5", 30)
    papers = [_paper("2401.00001"), _paper("2401.00002")]

    raw = json.dumps({"concepts": ["LLM"], "methods": [], "datasets": []})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": raw}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.graph.extractors.ollama.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await extractor.extract_batch(papers, concurrency=2)

    assert "2401.00001" in results
    assert "2401.00002" in results


async def test_ollama_extract_batch_empty_papers() -> None:
    extractor = OllamaExtractor("http://localhost:11434", "qwen2.5", 30)
    results = await extractor.extract_batch([], concurrency=1)
    assert results == {}
