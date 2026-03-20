"""Unit tests for TopicClusterer."""
from __future__ import annotations

from app.analytics.topic_clusterer import TopicClusterer, _shared_prefix_len


# ---------------------------------------------------------------------------
# _shared_prefix_len helper
# ---------------------------------------------------------------------------

def test_shared_prefix_len_identical_strings() -> None:
    assert _shared_prefix_len("attention", "attention") == 9


def test_shared_prefix_len_partial_match() -> None:
    # "attention" vs "attend": a-t-t-e-n match, then 't' vs 'd' diverge → 5
    assert _shared_prefix_len("attention", "attend") == 5


def test_shared_prefix_len_partial_match_two_chars() -> None:
    # "neural" vs "network": n-e match, then 'u' vs 't' diverge → 2
    assert _shared_prefix_len("neural", "network") == 2


def test_shared_prefix_len_empty_string() -> None:
    assert _shared_prefix_len("", "foo") == 0
    assert _shared_prefix_len("foo", "") == 0


# ---------------------------------------------------------------------------
# TopicClusterer.cluster_keywords
# ---------------------------------------------------------------------------

def test_cluster_keywords_groups_by_shared_prefix() -> None:
    clusterer = TopicClusterer()
    keywords = ["attention_mechanism", "attention_head", "neural_network"]
    result = clusterer.cluster_keywords(keywords)

    # "atten" (≥4 chars) shared → both attention_* in the same cluster
    attention_cluster = next(v for v in result.values() if len(v) == 2)
    assert "attention_mechanism" in attention_cluster
    assert "attention_head" in attention_cluster


def test_cluster_keywords_singleton_becomes_own_cluster() -> None:
    clusterer = TopicClusterer()
    result = clusterer.cluster_keywords(["transformer"])
    assert "transformer" in result
    assert result["transformer"] == ["transformer"]


def test_cluster_keywords_empty_input() -> None:
    clusterer = TopicClusterer()
    assert clusterer.cluster_keywords([]) == {}


def test_cluster_keywords_no_shared_prefix() -> None:
    clusterer = TopicClusterer()
    keywords = ["alpha_one", "beta_two", "gamma_three", "delta_four"]
    result = clusterer.cluster_keywords(keywords)
    # No pair shares ≥4 chars prefix → each is its own cluster
    assert len(result) == 4


def test_cluster_keywords_returns_all_keywords() -> None:
    clusterer = TopicClusterer()
    keywords = ["deep_learning", "deep_network", "reinforcement_learning", "recurrent_net"]
    result = clusterer.cluster_keywords(keywords)
    all_members = [kw for members in result.values() for kw in members]
    assert sorted(all_members) == sorted(keywords)
