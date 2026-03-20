"""Bridge node detector — loads AGE Concept subgraph into networkx and computes
approximate betweenness centrality.

CRITICAL: full betweenness is O(n³). Always use k=min(k_samples, len(G)) to
sample at most k_samples pivot nodes, keeping runtime linear in k.
"""
from __future__ import annotations

from datetime import UTC, datetime

import networkx as nx  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.models import BridgeNodeScore
from app.graph.schemas import BridgeNodeResult

log = get_logger(__name__)

_GRAPH = "research_graph"

_CONCEPT_EDGE_QUERY = f"""
SELECT * FROM cypher('{_GRAPH}', $$
  MATCH (a:Concept)-[r]->(b:Concept)
  RETURN a.name, type(r), b.name
$$) AS (source agtype, rel_type agtype, target agtype);
"""


def _strip_agtype(value: str) -> str:
    """AGE returns string values as JSON-quoted strings — strip surrounding quotes."""
    s = value.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


class BridgeNodeDetector:
    """Loads the Concept subgraph from AGE into networkx and scores centrality.

    Args:
        k_samples: Max pivot nodes for approximate betweenness (default: from settings).
    """

    def __init__(self, k_samples: int = 100) -> None:
        self._k_samples = k_samples

    async def compute(
        self,
        session: AsyncSession,
        top_n: int = 20,
    ) -> list[BridgeNodeResult]:
        """Compute approximate betweenness centrality for Concept nodes.

        Returns top_n results sorted by centrality score descending.
        Stores results in bridge_node_scores (upsert).
        """
        # Build networkx DiGraph from AGE
        G: nx.DiGraph = nx.DiGraph()
        rows = (await session.execute(text(_CONCEPT_EDGE_QUERY))).all()
        for row in rows:
            src = _strip_agtype(str(row[0]))
            tgt = _strip_agtype(str(row[2]))
            G.add_edge(src, tgt)

        node_count = G.number_of_nodes()
        edge_count = G.number_of_edges()

        log.info(
            "bridge_node_detector_graph_loaded",
            node_count=node_count,
            edge_count=edge_count,
        )

        if node_count == 0:
            return []

        k = min(self._k_samples, node_count)
        centrality: dict[str, float] = nx.betweenness_centrality(
            G,
            k=k,
            normalized=True,
            seed=42,
        )

        # Sort and take top_n
        ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
        computed_at = datetime.now(UTC)

        results: list[BridgeNodeResult] = []
        rows_to_upsert = []
        for concept_name, score in ranked:
            results.append(
                BridgeNodeResult(
                    concept_name=concept_name,
                    centrality_score=score,
                    graph_node_count=node_count,
                    graph_edge_count=edge_count,
                )
            )
            rows_to_upsert.append(
                {
                    "concept_name": concept_name,
                    "centrality_score": score,
                    "graph_node_count": node_count,
                    "graph_edge_count": edge_count,
                    "computed_at": computed_at,
                }
            )

        if rows_to_upsert:
            stmt = pg_insert(BridgeNodeScore).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_update(
                index_elements=["concept_name"],
                set_={
                    "centrality_score": stmt.excluded.centrality_score,
                    "graph_node_count": stmt.excluded.graph_node_count,
                    "graph_edge_count": stmt.excluded.graph_edge_count,
                    "computed_at": stmt.excluded.computed_at,
                },
            )
            await session.execute(stmt)

        log.info(
            "bridge_node_detector_done",
            results_count=len(results),
            top_concept=results[0].concept_name if results else None,
        )
        return results
