"""Unit tests for app/services/rag.py"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag import PaperResult, get_context_for_text, search_similar


def _make_row(i: int) -> dict:
    return {
        "paper_id": i,
        "arxiv_id": f"2401.{i:05d}",
        "title": f"Paper {i}",
        "abstract_snippet": f"Snippet {i}",
        "score": 0.9 - i * 0.05,
        "published_at": datetime(2024, 1, i + 1, tzinfo=UTC),
    }


async def test_search_similar_returns_results() -> None:
    row = _make_row(1)
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = [row]

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_similar([0.1, 0.2, 0.3], top_k=5, min_score=0.7, db=mock_db)

    assert len(results) == 1
    assert isinstance(results[0], PaperResult)
    assert results[0].paper_id == 1
    assert results[0].title == "Paper 1"


async def test_search_similar_empty_result() -> None:
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = []

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_similar([0.1, 0.2], top_k=5, min_score=0.9, db=mock_db)

    assert results == []


async def test_search_similar_formats_vector_correctly() -> None:
    """Verify the vector is formatted as a Postgres-compatible string."""
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = []
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    await search_similar([1.0, 2.5, -0.3], top_k=3, min_score=0.5, db=mock_db)

    call_args = mock_db.execute.call_args
    params = call_args[0][1]
    assert params["query_vec"] == "[1.0,2.5,-0.3]"
    assert params["top_k"] == 3
    assert params["min_score"] == 0.5


async def test_get_context_for_text_calls_embedding_then_search() -> None:
    vector = [0.1, 0.2, 0.3]
    row = _make_row(1)
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = [row]
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.rag.emb.get_embedding", AsyncMock(return_value=vector)):
        results = await get_context_for_text("test query", top_k=5, min_score=0.7, db=mock_db)

    assert len(results) == 1
    assert results[0].paper_id == 1


async def test_get_context_for_text_returns_empty_when_no_matches() -> None:
    vector = [0.1, 0.2]
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = []
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.rag.emb.get_embedding", AsyncMock(return_value=vector)):
        results = await get_context_for_text("nothing matches", top_k=5, min_score=0.99, db=mock_db)

    assert results == []


async def test_search_similar_multiple_results_preserves_order() -> None:
    rows = [_make_row(1), _make_row(2), _make_row(3)]
    mock_mapping = MagicMock()
    mock_mapping.all.return_value = rows
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_similar([0.5] * 5, top_k=3, min_score=0.5, db=mock_db)

    assert len(results) == 3
    assert [r.paper_id for r in results] == [1, 2, 3]
