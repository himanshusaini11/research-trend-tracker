"""Relation builder — writes Paper, Concept, and Author nodes and edges to AGE.

AGE constraints:
- cypher() calls must be: SELECT * FROM cypher('graph', $$ ... $$) AS (col agtype)
- Parameters cannot be interpolated directly — sanitize before f-string injection
- MERGE is used for idempotency
- search_path must include ag_catalog for every session that runs cypher()
"""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.models import PaperCitation
from app.graph.schemas import EntityExtractionResult

log = get_logger(__name__)

_GRAPH = "research_graph"
_MAX_LABEL_LEN = 200
_UNSAFE = str.maketrans({"'": None, "\\": None, "$": None, "\n": " ", "\r": " "})


def _s(value: str) -> str:
    """Sanitize a string for safe interpolation into a cypher f-string."""
    return value.translate(_UNSAFE)[:_MAX_LABEL_LEN].strip()


class RelationBuilder:
    """Builds graph nodes and edges in Apache AGE from entity extraction results.

    Args:
        session: An ``AsyncSession`` already configured to use the AGE extension.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def setup(self) -> None:
        """Load AGE and set search_path for this session — must be called first."""
        await self._session.execute(text("LOAD 'age';"))
        await self._session.execute(
            text('SET search_path = ag_catalog, "$user", public;')
        )

    async def build_for_paper(
        self,
        arxiv_id: str,
        title: str,
        year: int | None,
        authors: list[tuple[str, str]],  # (author_id, author_name)
        result: EntityExtractionResult,
    ) -> tuple[int, int]:
        """Build all nodes and edges for one paper.

        Returns:
            (concepts_created, edges_created) — counts of MERGE operations issued.
        """
        concepts_created = 0
        edges_created = 0

        aid = _s(arxiv_id)
        ttl = _s(title)
        yr = str(year) if year else "null"

        # Paper node
        await self._cypher(
            f"MERGE (p:Paper {{arxiv_id: '{aid}', title: '{ttl}', year: {yr}}}) RETURN p",
            "p",
        )

        # Author nodes + BY edges
        for author_id, author_name in authors:
            a_id = _s(author_id)
            a_name = _s(author_name)
            await self._cypher(
                f"MERGE (a:Author {{author_id: '{a_id}', name: '{a_name}'}}) RETURN a",
                "a",
            )
            await self._cypher(
                f"MATCH (p:Paper {{arxiv_id: '{aid}'}}), (a:Author {{author_id: '{a_id}'}}) "
                f"MERGE (p)-[:BY]->(a) RETURN p",
                "p",
            )
            edges_created += 1

        # Concept nodes + MENTIONS edges
        for concept in result.concepts:
            c = _s(concept)
            if not c:
                continue
            await self._cypher(
                f"MERGE (c:Concept {{name: '{c}'}}) RETURN c",
                "c",
            )
            await self._cypher(
                f"MATCH (p:Paper {{arxiv_id: '{aid}'}}), (c:Concept {{name: '{c}'}}) "
                f"MERGE (p)-[:MENTIONS]->(c) RETURN p",
                "p",
            )
            concepts_created += 1
            edges_created += 1

        # Method nodes + USES_METHOD edges
        for method in result.methods:
            m = _s(method)
            if not m:
                continue
            await self._cypher(
                f"MERGE (c:Concept {{name: '{m}'}}) RETURN c",
                "c",
            )
            await self._cypher(
                f"MATCH (p:Paper {{arxiv_id: '{aid}'}}), (c:Concept {{name: '{m}'}}) "
                f"MERGE (p)-[:USES_METHOD]->(c) RETURN p",
                "p",
            )
            concepts_created += 1
            edges_created += 1

        # CITES edges from paper_citations table
        cit_rows = (
            await self._session.execute(
                select(PaperCitation.cited_paper_id).where(
                    PaperCitation.source_arxiv_id == arxiv_id,
                    PaperCitation.citation_type == "citation",
                )
            )
        ).scalars().all()

        for cited_id in cit_rows:
            c_id = _s(cited_id)
            # Ensure target paper node exists (minimal stub — no title yet)
            await self._cypher(
                f"MERGE (p2:Paper {{arxiv_id: '{c_id}'}}) RETURN p2",
                "p2",
            )
            await self._cypher(
                f"MATCH (p:Paper {{arxiv_id: '{aid}'}}), (p2:Paper {{arxiv_id: '{c_id}'}}) "
                f"MERGE (p)-[:CITES]->(p2) RETURN p",
                "p",
            )
            edges_created += 1

        log.info(
            "relation_builder_paper_done",
            arxiv_id=arxiv_id,
            concepts_created=concepts_created,
            edges_created=edges_created,
        )
        return concepts_created, edges_created

    async def build_concept_cooccurrence(self, arxiv_id: str) -> None:
        """Create CO_OCCURS_WITH edges between every pair of Concept nodes
        that co-occur in the same paper (share a MENTIONS edge from it).
        """
        aid = _s(arxiv_id)
        await self._cypher(
            f"MATCH (p:Paper {{arxiv_id: '{aid}'}})-[:MENTIONS]->(c1:Concept) "
            f"MATCH (p)-[:MENTIONS]->(c2:Concept) "
            f"WHERE c1 <> c2 "
            f"MERGE (c1)-[:CO_OCCURS_WITH]->(c2) "
            f"RETURN c1",
            "c1",
        )

    async def _cypher(self, query: str, return_col: str) -> None:
        """Execute a single cypher statement via AGE's SQL wrapper.

        Uses exec_driver_sql instead of text() so SQLAlchemy does not
        interpret AGE relationship-type labels (e.g. :MENTIONS) as bind
        parameters.
        """
        sql = (
            f"SELECT * FROM cypher('{_GRAPH}', $$ {query} $$)"
            f" AS ({return_col} agtype);"
        )
        conn = await self._session.connection()
        await conn.exec_driver_sql(sql)
