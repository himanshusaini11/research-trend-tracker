"""Unit tests for pure functions in app/tasks/process_paper.py"""
from __future__ import annotations

import pytest

from app.tasks.process_paper import _build_edges, _extract_concepts


# ---------------------------------------------------------------------------
# _extract_concepts
# ---------------------------------------------------------------------------

def test_extract_concepts_returns_top_n() -> None:
    text = " ".join(["neural"] * 50 + ["network"] * 30 + ["transformer"] * 20 + ["attention"] * 10)
    results = _extract_concepts(text, top_n=3)
    assert len(results) == 3
    concepts = [c for c, _ in results]
    assert "neural" in concepts
    assert "network" in concepts
    assert "transformer" in concepts


def test_extract_concepts_weights_sum_lte_one() -> None:
    text = "deep learning neural networks transformers attention mechanisms gradient descent"
    results = _extract_concepts(text, top_n=50)
    total_weight = sum(w for _, w in results)
    assert total_weight <= 1.0 + 1e-9


def test_extract_concepts_filters_stopwords() -> None:
    text = "the and or but in on at for of with by from is are was"
    results = _extract_concepts(text, top_n=50)
    concepts = [c for c, _ in results]
    for stopword in ("the", "and", "or", "but", "for", "with"):
        assert stopword not in concepts


def test_extract_concepts_filters_short_tokens() -> None:
    text = "go is an do language learning neural"
    results = _extract_concepts(text, top_n=50)
    concepts = [c for c, _ in results]
    # tokens < 3 chars should not appear (regex requires len >= 3)
    for c in concepts:
        assert len(c) >= 3


def test_extract_concepts_empty_text() -> None:
    results = _extract_concepts("", top_n=10)
    assert results == []


def test_extract_concepts_text_with_only_stopwords() -> None:
    text = "the and or but in on at to for of with by from"
    results = _extract_concepts(text, top_n=10)
    # all filtered out — nothing remains after stopword removal
    assert results == []


def test_extract_concepts_returns_normalized_weights() -> None:
    text = "learning " * 10
    results = _extract_concepts(text, top_n=5)
    assert len(results) == 1
    concept, weight = results[0]
    assert concept == "learning"
    assert abs(weight - 1.0) < 1e-9  # sole token → weight = count/total = 1.0


# ---------------------------------------------------------------------------
# _build_edges
# ---------------------------------------------------------------------------

def test_build_edges_returns_pairs() -> None:
    concepts = [(f"concept{i}", 0.1) for i in range(5)]
    edges = _build_edges(concepts)
    # C(5,2) = 10 pairs
    assert len(edges) == 10


def test_build_edges_weight_is_product() -> None:
    concepts = [("alpha", 0.5), ("beta", 0.4)]
    edges = _build_edges(concepts)
    assert len(edges) == 1
    src, tgt, w = edges[0]
    assert src == "alpha"
    assert tgt == "beta"
    assert abs(w - round(0.5 * 0.4, 6)) < 1e-9


def test_build_edges_uses_top_20_only() -> None:
    concepts = [(f"concept{i}", 0.01) for i in range(25)]
    edges = _build_edges(concepts)
    # Only first 20 used → C(20,2) = 190 edges
    assert len(edges) == 190


def test_build_edges_empty_concepts() -> None:
    assert _build_edges([]) == []


def test_build_edges_single_concept() -> None:
    assert _build_edges([("learning", 0.5)]) == []


def test_build_edges_two_concepts() -> None:
    edges = _build_edges([("neural", 0.3), ("network", 0.2)])
    assert len(edges) == 1
    assert edges[0][0] == "neural"
    assert edges[0][1] == "network"
