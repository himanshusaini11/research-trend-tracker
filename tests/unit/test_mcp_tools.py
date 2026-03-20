"""Unit tests for new MCP tools: query_knowledge_graph and get_prediction_report."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge_node(name: str, centrality: float) -> MagicMock:
    row = MagicMock()
    row.concept_name = name
    row.centrality_score = centrality
    row.graph_node_count = 10
    row.graph_edge_count = 20
    row.computed_at = datetime(2024, 6, 1, tzinfo=UTC)
    return row


def _make_velocity(name: str, velocity: float, trend: str = "accelerating") -> MagicMock:
    row = MagicMock()
    row.concept_name = name
    row.velocity = velocity
    row.acceleration = 0.5
    row.trend = trend
    row.weeks_of_data = 4
    row.computed_at = datetime(2024, 6, 1, tzinfo=UTC)
    return row


def _make_joined_row(name: str, centrality: float, velocity: float, trend: str = "accelerating"):
    """Simulate a row from a JOIN query returning (BridgeNodeScore, VelocityScore)."""
    return (_make_bridge_node(name, centrality), _make_velocity(name, velocity, trend))


def _make_prediction_row(topic: str = "AI/ML research") -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.topic_context = topic
    row.report = {
        "emerging_directions": [],
        "underexplored_gaps": [],
        "predicted_convergences": [],
        "overall_confidence": "high",
    }
    row.model_name = "llama3.2"
    row.generated_at = datetime(2024, 6, 10, tzinfo=UTC)
    row.is_validated = False
    return row


def _mock_session_for_join(rows: list) -> AsyncMock:
    """Return a mock AsyncSessionLocal context manager whose execute returns joined rows."""
    result_mock = MagicMock()
    result_mock.all.return_value = rows

    execute_result = MagicMock()
    execute_result.all.return_value = rows  # for JOIN queries that call .all()

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


def _mock_session_for_scalar(row) -> AsyncMock:
    """Return a mock AsyncSessionLocal context manager for scalar queries."""
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = row

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# query_knowledge_graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_knowledge_graph_returns_top_n() -> None:
    """Limit is applied: requesting top_n=2 from 5 rows returns 2 items."""
    from app.mcp_server.tools import query_knowledge_graph

    rows = [
        _make_joined_row("alpha", 0.9, 5.0),
        _make_joined_row("beta", 0.7, 4.0),
        _make_joined_row("gamma", 0.5, 3.0),
        _make_joined_row("delta", 0.3, 2.0),
        _make_joined_row("epsilon", 0.1, 1.0),
    ]
    mock_session = _mock_session_for_join(rows)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await query_knowledge_graph(top_n=2)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_query_knowledge_graph_returns_concept_signal_fields() -> None:
    """Each result dict contains all ConceptSignal fields."""
    from app.mcp_server.tools import query_knowledge_graph

    rows = [_make_joined_row("attention", 0.8, 3.0, "accelerating")]
    mock_session = _mock_session_for_join(rows)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await query_knowledge_graph(top_n=10)

    assert len(result) == 1
    item = result[0]
    assert item["concept_name"] == "attention"
    assert "centrality_score" in item
    assert "velocity" in item
    assert "acceleration" in item
    assert "trend" in item
    assert "composite_score" in item


@pytest.mark.asyncio
async def test_query_knowledge_graph_filters_by_trend() -> None:
    """trend_filter='accelerating' excludes decelerating and stable rows."""
    from app.mcp_server.tools import query_knowledge_graph

    rows = [
        _make_joined_row("fast", 0.9, 5.0, "accelerating"),
        _make_joined_row("slow", 0.5, -2.0, "decelerating"),
        _make_joined_row("flat", 0.3, 0.0, "stable"),
    ]
    # The WHERE clause filters in the DB — simulate by returning only matching rows
    filtered = [r for r in rows if r[1].trend == "accelerating"]
    mock_session = _mock_session_for_join(filtered)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await query_knowledge_graph(top_n=20, trend_filter="accelerating")

    assert all(r["trend"] == "accelerating" for r in result)
    assert len(result) == 1
    assert result[0]["concept_name"] == "fast"


@pytest.mark.asyncio
async def test_query_knowledge_graph_empty_returns_empty_list() -> None:
    """No rows in DB → returns empty list (not an error)."""
    from app.mcp_server.tools import query_knowledge_graph

    mock_session = _mock_session_for_join([])

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await query_knowledge_graph(top_n=20)

    assert result == []


@pytest.mark.asyncio
async def test_query_knowledge_graph_composite_score_in_range() -> None:
    """composite_score is between 0.0 and 1.0 inclusive."""
    from app.mcp_server.tools import query_knowledge_graph

    rows = [
        _make_joined_row("a", 0.9, 5.0),
        _make_joined_row("b", 0.1, 1.0),
    ]
    mock_session = _mock_session_for_join(rows)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await query_knowledge_graph(top_n=10)

    for item in result:
        assert 0.0 <= item["composite_score"] <= 1.0


# ---------------------------------------------------------------------------
# get_prediction_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prediction_report_returns_latest() -> None:
    """Returns report dict when a row exists."""
    from app.mcp_server.tools import get_prediction_report

    db_row = _make_prediction_row()
    mock_session = _mock_session_for_scalar(db_row)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await get_prediction_report(topic_context="AI/ML research")

    assert result["topic_context"] == "AI/ML research"
    assert "report" in result
    assert result["report"]["overall_confidence"] == "high"
    assert "generated_at" in result
    assert "model_name" in result


@pytest.mark.asyncio
async def test_get_prediction_report_no_reports() -> None:
    """Returns empty dict gracefully when no rows exist."""
    from app.mcp_server.tools import get_prediction_report

    mock_session = _mock_session_for_scalar(None)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await get_prediction_report(topic_context="unknown topic")

    assert result == {}


@pytest.mark.asyncio
async def test_get_prediction_report_includes_id() -> None:
    """Result includes a string representation of the UUID id."""
    from app.mcp_server.tools import get_prediction_report

    db_row = _make_prediction_row()
    expected_id = str(db_row.id)
    mock_session = _mock_session_for_scalar(db_row)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        result = await get_prediction_report()

    assert result["id"] == expected_id


@pytest.mark.asyncio
async def test_get_prediction_report_uses_topic_context_filter() -> None:
    """Session.execute is called exactly once (verifies query is issued)."""
    from app.mcp_server.tools import get_prediction_report

    db_row = _make_prediction_row(topic="NLP research")
    mock_session = _mock_session_for_scalar(db_row)

    with patch("app.mcp_server.tools.AsyncSessionLocal", return_value=mock_session):
        await get_prediction_report(topic_context="NLP research")

    mock_session.execute.assert_awaited_once()
