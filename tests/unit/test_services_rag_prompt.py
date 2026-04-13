"""Unit tests for app/services/rag_prompt.py"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.rag import PaperResult
from app.services.rag_prompt import build_prediction_prompt, build_search_summary_prompt


def _source(i: int) -> PaperResult:
    return PaperResult(
        paper_id=i,
        arxiv_id=f"2401.{i:05d}",
        title=f"Paper {i} Title",
        abstract_snippet=f"Abstract snippet for paper {i}.",
        score=0.9,
        published_at=datetime(2024, 1, i + 1, tzinfo=UTC),
    )


def test_prediction_prompt_contains_numbered_sources() -> None:
    sources = [_source(1), _source(2)]
    prompt = build_prediction_prompt("Trend text", sources)
    assert "[1]" in prompt
    assert "[2]" in prompt
    assert "Paper 1 Title" in prompt
    assert "Paper 2 Title" in prompt


def test_prediction_prompt_contains_prediction_text() -> None:
    prompt = build_prediction_prompt("LLM will dominate AI research", [_source(1)])
    assert "LLM will dominate AI research" in prompt
    assert "Prediction to analyse" in prompt


def test_prediction_prompt_empty_sources() -> None:
    prompt = build_prediction_prompt("Some prediction", [])
    assert "Some prediction" in prompt
    assert "Sources:" in prompt
    # With no sources, no numbered source entries appear (only the citation instruction mentions [1])
    assert "Paper" not in prompt


def test_prediction_prompt_includes_date() -> None:
    prompt = build_prediction_prompt("text", [_source(0)])
    assert "2024-01-01" in prompt


def test_search_summary_prompt_contains_query() -> None:
    prompt = build_search_summary_prompt("diffusion models", [_source(1)])
    assert "diffusion models" in prompt
    assert "Query:" in prompt


def test_search_summary_prompt_numbered_sources() -> None:
    sources = [_source(1), _source(2), _source(3)]
    prompt = build_search_summary_prompt("transformers", sources)
    assert "[1]" in prompt
    assert "[2]" in prompt
    assert "[3]" in prompt


def test_search_summary_prompt_empty_sources() -> None:
    prompt = build_search_summary_prompt("graph neural networks", [])
    assert "graph neural networks" in prompt
    # No source entries — no paper titles appear
    assert "Paper" not in prompt


def test_search_summary_prompt_cite_instruction() -> None:
    prompt = build_search_summary_prompt("RL", [_source(1)])
    assert "Cite sources" in prompt
