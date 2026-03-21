"""Unit tests for BridgeNodeDetector — mocks AsyncSession + AGE query results."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.bridge_node_detector import BridgeNodeDetector, _strip_agtype
from app.graph.schemas import BridgeNodeResult


# ---------------------------------------------------------------------------
# _strip_agtype helper
# ---------------------------------------------------------------------------

def test_strip_agtype_removes_surrounding_quotes() -> None:
    assert _strip_agtype('"attention mechanism"') == "attention mechanism"


def test_strip_agtype_leaves_unquoted_string() -> None:
    assert _strip_agtype("transformer") == "transformer"


def test_strip_agtype_strips_whitespace_before_checking() -> None:
    assert _strip_agtype('  "bert"  ') == "bert"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(rows: list[tuple[str, str, str]]) -> AsyncMock:
    """Build a mock AsyncSession whose connection().exec_driver_sql() returns the given rows."""
    result_mock = MagicMock()
    result_mock.all.return_value = rows

    conn_mock = AsyncMock()
    # Three calls: LOAD 'age', SET search_path, then the actual Cypher query
    conn_mock.exec_driver_sql = AsyncMock(side_effect=[None, None, result_mock])

    session = AsyncMock()
    session.connection = AsyncMock(return_value=conn_mock)
    return session


# ---------------------------------------------------------------------------
# Empty graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_empty_graph_returns_empty_list() -> None:
    session = _make_session([])
    detector = BridgeNodeDetector(k_samples=10)
    results = await detector.compute(session, top_n=5)
    assert results == []


# ---------------------------------------------------------------------------
# Graph structure and centrality
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_builds_graph_and_returns_results() -> None:
    # Simple linear chain: A -> B -> C
    rows = [
        ('"node_a"', '"MENTIONS"', '"node_b"'),
        ('"node_b"', '"MENTIONS"', '"node_c"'),
    ]
    session = _make_session(rows)
    detector = BridgeNodeDetector(k_samples=10)
    results = await detector.compute(session, top_n=5)

    assert len(results) > 0
    assert all(isinstance(r, BridgeNodeResult) for r in results)
    # node_b is the bridge — highest centrality in a chain
    names = [r.concept_name for r in results]
    assert "node_b" in names


@pytest.mark.asyncio
async def test_compute_top_n_limits_results() -> None:
    # Build a larger graph: star topology with 6 leaf nodes
    rows = [('"hub"', '"MENTIONS"', f'"leaf_{i}"') for i in range(6)]
    session = _make_session(rows)
    detector = BridgeNodeDetector(k_samples=10)
    results = await detector.compute(session, top_n=3)

    assert len(results) <= 3


@pytest.mark.asyncio
async def test_compute_node_and_edge_counts_in_result() -> None:
    rows = [
        ('"a"', '"MENTIONS"', '"b"'),
        ('"b"', '"MENTIONS"', '"c"'),
        ('"a"', '"MENTIONS"', '"c"'),
    ]
    session = _make_session(rows)
    detector = BridgeNodeDetector(k_samples=10)
    results = await detector.compute(session, top_n=10)

    # All results share the same graph stats
    assert results[0].graph_node_count == 3
    assert results[0].graph_edge_count == 3


# ---------------------------------------------------------------------------
# k = min(k_samples, len(G))
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_uses_k_min_k_samples_and_graph_size() -> None:
    """With only 3 nodes and k_samples=100, k should be capped at 3."""
    rows = [('"a"', '"MENTIONS"', '"b"'), ('"b"', '"MENTIONS"', '"c"')]
    session = _make_session(rows)

    captured_k: list[int] = []

    import networkx as nx
    real_betweenness = nx.betweenness_centrality

    def _spy_betweenness(G, k=None, **kwargs):  # type: ignore[no-untyped-def]
        captured_k.append(k)
        return real_betweenness(G, k=k, **kwargs)

    with patch("app.graph.bridge_node_detector.nx.betweenness_centrality", _spy_betweenness):
        detector = BridgeNodeDetector(k_samples=100)
        await detector.compute(session, top_n=5)

    # 3 nodes, k_samples=100 → k should be min(100, 3) = 3
    assert captured_k == [3]


@pytest.mark.asyncio
async def test_compute_k_capped_at_k_samples_for_large_graph() -> None:
    """With 50 nodes and k_samples=10, k should be 10."""
    rows = [(f'"node_{i}"', '"MENTIONS"', f'"node_{i+1}"') for i in range(49)]
    session = _make_session(rows)

    captured_k: list[int] = []

    import networkx as nx
    real_betweenness = nx.betweenness_centrality

    def _spy_betweenness(G, k=None, **kwargs):  # type: ignore[no-untyped-def]
        captured_k.append(k)
        return real_betweenness(G, k=k, **kwargs)

    with patch("app.graph.bridge_node_detector.nx.betweenness_centrality", _spy_betweenness):
        detector = BridgeNodeDetector(k_samples=10)
        await detector.compute(session, top_n=5)

    assert captured_k == [10]


# ---------------------------------------------------------------------------
# Upsert called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_executes_upsert_for_results() -> None:
    rows = [('"a"', '"MENTIONS"', '"b"')]
    session = _make_session(rows)
    detector = BridgeNodeDetector(k_samples=10)
    await detector.compute(session, top_n=5)

    # session.execute called once for the upsert (AGE query uses conn.exec_driver_sql)
    assert session.execute.call_count >= 1
