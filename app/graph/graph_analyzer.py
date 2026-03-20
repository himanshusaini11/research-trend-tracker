"""Graph analyzer — orchestrates BridgeNodeDetector + VelocityTracker into a
single combined ConceptSignal list sorted by composite_score.

Composite score = 0.6 * normalized_centrality + 0.4 * normalized_velocity
(each signal normalized to [0, 1] before combining).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.velocity_tracker import VelocityTracker
from app.core.config import settings
from app.core.logger import get_logger
from app.graph.bridge_node_detector import BridgeNodeDetector
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
