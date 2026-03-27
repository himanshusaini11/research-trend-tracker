"""Graph analyzer — orchestrates BridgeNodeDetector + VelocityTracker into a
single combined ConceptSignal list sorted by composite_score.

Composite score = 0.6 * normalized_centrality + 0.4 * normalized_velocity
(each signal normalized to [0, 1] before combining).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.velocity_tracker import VelocityTracker
from app.core.config import settings
from app.core.logger import get_logger
from app.core.models import BridgeNodeScore, Paper, VelocityScore
from app.graph.bridge_node_detector import BridgeNodeDetector, _strip_agtype
from app.graph.schemas import BridgeNodeResult, ConceptSignal, VelocityResult

log = get_logger(__name__)


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. Returns all-zeros if range is zero."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


class GraphAnalyzer:
    """Combines betweenness centrality and velocity into a single ranked signal.

    Args:
        top_n: Number of top bridge-node concepts to analyse (default: from settings).
        k_samples: Pivot samples for approximate centrality (default: from settings).
    """

    def __init__(
        self,
        top_n: int | None = None,
        k_samples: int | None = None,
    ) -> None:
        self._top_n = top_n if top_n is not None else settings.graph_top_n_concepts
        self._k_samples = k_samples if k_samples is not None else settings.graph_centrality_k_samples

    async def analyze(self, session: AsyncSession) -> list[ConceptSignal]:
        """Run both detectors and return concepts ranked by composite_score."""
        detector = BridgeNodeDetector(k_samples=self._k_samples)
        bridge_results: list[BridgeNodeResult] = await detector.compute(
            session, top_n=self._top_n
        )

        if not bridge_results:
            return []

        concept_names = [r.concept_name for r in bridge_results]

        tracker = VelocityTracker()
        velocity_results: list[VelocityResult] = await tracker.compute(session, concept_names)

        # Index velocity results by concept_name
        velocity_by_name: dict[str, VelocityResult] = {
            v.concept_name: v for v in velocity_results
        }

        centrality_values = [r.centrality_score for r in bridge_results]
        velocity_values = [
            velocity_by_name[r.concept_name].velocity
            if r.concept_name in velocity_by_name
            else 0.0
            for r in bridge_results
        ]

        norm_centrality = _normalize(centrality_values)
        norm_velocity = _normalize(velocity_values)

        signals: list[ConceptSignal] = []
        for i, bridge in enumerate(bridge_results):
            vel = velocity_by_name.get(bridge.concept_name)
            composite = 0.6 * norm_centrality[i] + 0.4 * norm_velocity[i]
            signals.append(
                ConceptSignal(
                    concept_name=bridge.concept_name,
                    centrality_score=bridge.centrality_score,
                    velocity=vel.velocity if vel else 0.0,
                    acceleration=vel.acceleration if vel else 0.0,
                    trend=vel.trend if vel else "stable",
                    composite_score=composite,
                )
            )

        signals.sort(key=lambda s: s.composite_score, reverse=True)

        log.info(
            "graph_analyzer_done",
            signals_count=len(signals),
            top_concept=signals[0].concept_name if signals else None,
        )
        return signals

    async def read_signals(self, session: AsyncSession) -> list[ConceptSignal]:
        """Read pre-computed signals from bridge_node_scores + velocity_scores tables.

        This is the fast read path for the API — no AGE queries, no networkx.
        Returns an empty list if tables have not been populated yet.
        """
        bridge_rows = (
            await session.execute(
                select(BridgeNodeScore).order_by(BridgeNodeScore.centrality_score.desc())
            )
        ).scalars().all()

        if not bridge_rows:
            return []

        velocity_rows = (
            await session.execute(select(VelocityScore))
        ).scalars().all()

        velocity_by_name: dict[str, VelocityScore] = {
            v.concept_name: v for v in velocity_rows
        }

        centrality_values = [r.centrality_score for r in bridge_rows]
        velocity_values = [
            velocity_by_name[r.concept_name].velocity
            if r.concept_name in velocity_by_name
            else 0.0
            for r in bridge_rows
        ]

        norm_centrality = _normalize(centrality_values)
        norm_velocity   = _normalize(velocity_values)

        signals: list[ConceptSignal] = []
        for i, bridge in enumerate(bridge_rows):
            vel = velocity_by_name.get(bridge.concept_name)
            composite = 0.6 * norm_centrality[i] + 0.4 * norm_velocity[i]
            signals.append(
                ConceptSignal(
                    concept_name=bridge.concept_name,
                    centrality_score=bridge.centrality_score,
                    velocity=vel.velocity if vel else 0.0,
                    acceleration=vel.acceleration if vel else 0.0,
                    trend=vel.trend if vel else "stable",
                    composite_score=composite,
                )
            )

        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals[: self._top_n]

    async def read_signals_page(
        self,
        session: AsyncSession,
        limit: int,
        offset: int,
    ) -> list[ConceptSignal]:
        """Paginated read of pre-computed signals — for incremental graph loading.

        Normalization is always performed across all rows so composite scores
        remain consistent regardless of which page is requested.
        """
        bridge_rows = (
            await session.execute(
                select(BridgeNodeScore).order_by(BridgeNodeScore.centrality_score.desc())
            )
        ).scalars().all()

        if not bridge_rows or offset >= len(bridge_rows):
            return []

        velocity_rows = (await session.execute(select(VelocityScore))).scalars().all()
        velocity_by_name: dict[str, VelocityScore] = {v.concept_name: v for v in velocity_rows}

        centrality_values = [r.centrality_score for r in bridge_rows]
        velocity_values = [
            velocity_by_name[r.concept_name].velocity
            if r.concept_name in velocity_by_name
            else 0.0
            for r in bridge_rows
        ]
        norm_centrality = _normalize(centrality_values)
        norm_velocity   = _normalize(velocity_values)

        signals: list[ConceptSignal] = []
        for i, bridge in enumerate(bridge_rows):
            vel = velocity_by_name.get(bridge.concept_name)
            composite = 0.6 * norm_centrality[i] + 0.4 * norm_velocity[i]
            signals.append(
                ConceptSignal(
                    concept_name=bridge.concept_name,
                    centrality_score=bridge.centrality_score,
                    velocity=vel.velocity if vel else 0.0,
                    acceleration=vel.acceleration if vel else 0.0,
                    trend=vel.trend if vel else "stable",
                    composite_score=composite,
                )
            )

        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals[offset: offset + limit]

    async def read_signals_for_date_range(
        self,
        session: AsyncSession,
        paper_from: str,
        paper_to: str,
    ) -> list[ConceptSignal]:
        """Return concept signals for papers published within a date range.

        Centrality is approximated by mention count within the paper subset.
        Velocity is still global (from velocity_scores table).
        Used for model-comparison views (e.g. show only qwen3.5:27b-extracted concepts).
        """
        dt_from = datetime.fromisoformat(paper_from).replace(tzinfo=timezone.utc)
        dt_to   = datetime.fromisoformat(paper_to).replace(tzinfo=timezone.utc)

        paper_ids: list[str] = list(
            (
                await session.execute(
                    select(Paper.arxiv_id).where(
                        and_(
                            Paper.published_at >= dt_from,
                            Paper.published_at < dt_to,
                        )
                    )
                )
            ).scalars().all()
        )

        if not paper_ids:
            return []

        conn = await session.connection()
        await conn.exec_driver_sql("LOAD 'age'")
        await conn.exec_driver_sql('SET search_path = ag_catalog, "$user", public')

        # Build safe IN list — arxiv IDs contain only digits, dots, and letters
        ids_literal = ", ".join(f"'{pid.replace(chr(39), '')}'" for pid in paper_ids)
        cypher_sql = f"""
            SELECT * FROM cypher('research_graph', $$
                MATCH (p:Paper)-[:MENTIONS]->(c:Concept)
                WHERE p.arxiv_id IN [{ids_literal}]
                RETURN c.name, count(*)
            $$) AS (concept_name agtype, cnt agtype)
        """
        raw_rows = (await conn.exec_driver_sql(cypher_sql)).all()
        # Sort by mention count descending in Python, take top N * 3 candidates
        rows = sorted(
            raw_rows,
            key=lambda r: float(_strip_agtype(str(r[1]))),
            reverse=True,
        )[: self._top_n * 3]

        velocity_rows = (await session.execute(select(VelocityScore))).scalars().all()
        velocity_by_name = {v.concept_name: v for v in velocity_rows}

        mention_counts = [float(_strip_agtype(str(r[1]))) for r in rows]
        velocity_vals = [
            velocity_by_name[_strip_agtype(str(r[0]))].velocity
            if _strip_agtype(str(r[0])) in velocity_by_name
            else 0.0
            for r in rows
        ]
        norm_counts = _normalize(mention_counts)
        norm_vel    = _normalize(velocity_vals)

        signals: list[ConceptSignal] = []
        for i, row in enumerate(rows):
            concept_name = _strip_agtype(str(row[0]))
            vel = velocity_by_name.get(concept_name)
            composite = 0.6 * norm_counts[i] + 0.4 * norm_vel[i]
            signals.append(
                ConceptSignal(
                    concept_name=concept_name,
                    centrality_score=mention_counts[i],
                    velocity=vel.velocity if vel else 0.0,
                    acceleration=vel.acceleration if vel else 0.0,
                    trend=vel.trend if vel else "stable",
                    composite_score=composite,
                )
            )

        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals[: self._top_n]
