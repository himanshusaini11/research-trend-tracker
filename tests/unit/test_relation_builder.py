"""Unit tests for RelationBuilder — mocks AsyncSession, verifies cypher strings."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graph.relation_builder import RelationBuilder, _s
from app.graph.schemas import EntityExtractionResult


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    # scalars().all() for the citation query
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock
    return session


def _empty_result(arxiv_id: str = "2401.00001") -> EntityExtractionResult:
    return EntityExtractionResult(
        arxiv_id=arxiv_id, concepts=[], methods=[], datasets=[]
    )


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------

def test_s_strips_single_quotes() -> None:
    assert "'" not in _s("it's a test")


def test_s_strips_backslash() -> None:
    assert "\\" not in _s("back\\slash")


def test_s_strips_dollar_sign() -> None:
    assert "$" not in _s("cost $100")


def test_s_replaces_newline_with_space() -> None:
    result = _s("line1\nline2")
    assert "\n" not in result
    assert " " in result


def test_s_truncates_to_200_chars() -> None:
    long = "x" * 300
    assert len(_s(long)) <= 200


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_executes_load_and_search_path() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    await builder.setup()

    calls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("LOAD 'age'" in c for c in calls)
    assert any("search_path" in c for c in calls)


# ---------------------------------------------------------------------------
# Paper node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_creates_paper_node() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="My Paper",
        year=2024,
        authors=[],
        result=_empty_result(),
    )

    executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("MERGE (p:Paper" in s and "2401.00001" in s for s in executed_sqls)


@pytest.mark.asyncio
async def test_build_paper_null_year() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    await builder.build_for_paper(
        arxiv_id="2401.00002",
        title="No Year",
        year=None,
        authors=[],
        result=_empty_result("2401.00002"),
    )

    executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("year: null" in s for s in executed_sqls)


# ---------------------------------------------------------------------------
# Author nodes + BY edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_creates_author_node_and_by_edge() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=[("auth-1", "Alice Smith")],
        result=_empty_result(),
    )

    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("MERGE (a:Author" in s and "Alice Smith" in s for s in sqls)
    assert any("MERGE (p)-[:BY]->(a)" in s for s in sqls)


@pytest.mark.asyncio
async def test_build_multiple_authors_all_merged() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    authors = [("a1", "Alice"), ("a2", "Bob"), ("a3", "Carol")]
    _, edges = await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=authors,
        result=_empty_result(),
    )

    # One BY edge per author
    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    by_edges = [s for s in sqls if "MERGE (p)-[:BY]->(a)" in s]
    assert len(by_edges) == 3
    assert edges >= 3


# ---------------------------------------------------------------------------
# Concept nodes + MENTIONS edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_creates_concept_nodes_and_mentions_edges() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    result = EntityExtractionResult(
        arxiv_id="2401.00001",
        concepts=["attention mechanism", "knowledge graph"],
        methods=[],
        datasets=[],
    )
    concepts, edges = await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=[],
        result=result,
    )

    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("attention mechanism" in s and "MERGE (c:Concept" in s for s in sqls)
    assert any("MERGE (p)-[:MENTIONS]->(c)" in s for s in sqls)
    assert concepts == 2
    assert edges == 2


# ---------------------------------------------------------------------------
# Method nodes + USES_METHOD edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_creates_method_nodes_and_uses_method_edges() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    result = EntityExtractionResult(
        arxiv_id="2401.00001",
        concepts=[],
        methods=["BERT", "gradient descent"],
        datasets=[],
    )
    concepts, edges = await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=[],
        result=result,
    )

    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("BERT" in s and "MERGE (c:Concept" in s for s in sqls)
    assert any("MERGE (p)-[:USES_METHOD]->(c)" in s for s in sqls)
    assert concepts == 2
    assert edges == 2


# ---------------------------------------------------------------------------
# CITES edges from paper_citations table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_creates_cites_edges_from_db() -> None:
    session = _mock_session()

    # First call is paper node, further calls for author/concept — the citations
    # query returns ["cited-abc"]
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = ["cited-abc"]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock

    builder = RelationBuilder(session)
    _, edges = await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=[],
        result=_empty_result(),
    )

    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("MERGE (p2:Paper" in s and "cited-abc" in s for s in sqls)
    assert any("MERGE (p)-[:CITES]->(p2)" in s for s in sqls)
    assert edges >= 1


# ---------------------------------------------------------------------------
# Sanitizer applied to cypher strings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_sanitizes_title_with_quotes() -> None:
    session = _mock_session()
    builder = RelationBuilder(session)
    await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="It's a paper about $money\\things",
        year=2024,
        authors=[],
        result=_empty_result(),
    )

    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    paper_merge = next(s for s in sqls if "MERGE (p:Paper" in s)
    # Original dangerous chars must be stripped from the injected value
    assert "It's" not in paper_merge   # apostrophe removed from title
    assert "\\\\things" not in paper_merge  # backslash removed
    # The sanitized value should appear without the dangerous chars
    assert "moneythings" in paper_merge


@pytest.mark.asyncio
async def test_empty_concept_skipped() -> None:
    """Concepts that reduce to empty string after sanitizing are skipped."""
    session = _mock_session()
    builder = RelationBuilder(session)
    # concept that is all stripped chars
    result = EntityExtractionResult(
        arxiv_id="2401.00001",
        concepts=["", "   "],
        methods=[],
        datasets=[],
    )
    concepts, _ = await builder.build_for_paper(
        arxiv_id="2401.00001",
        title="T",
        year=2024,
        authors=[],
        result=result,
    )
    assert concepts == 0
