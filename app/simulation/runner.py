"""SimulationRunner — orchestrates per-direction simulations into a SimulationReport."""
from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.graph.schemas import AdoptionReport, PredictionReport, SimulationReport
from app.simulation.engine import run_direction_simulation
from app.simulation.grounding import get_agent_context

log = get_logger(__name__)

_DEFAULT_RAG_TOP_K: int = 5
_DEFAULT_RAG_MIN_SCORE: float = 0.6
_DEFAULT_MAX_ROUNDS: int = 3


class SimulationRunner:
    """Runs multi-agent adoption simulation across all emerging directions."""

    def __init__(
        self,
        max_rounds: int = _DEFAULT_MAX_ROUNDS,
        rag_top_k: int = _DEFAULT_RAG_TOP_K,
        rag_min_score: float = _DEFAULT_RAG_MIN_SCORE,
    ) -> None:
        self._max_rounds = max_rounds
        self._rag_top_k = rag_top_k
        self._rag_min_score = rag_min_score

    async def run(
        self,
        prediction_report: PredictionReport,
        topic_context: str,
        db: AsyncSession,
        prediction_report_id: str | None = None,
    ) -> SimulationReport:
        """Run simulation for every emerging direction in the prediction report.

        Per-direction failures are caught and logged; the remaining directions
        still complete so a partial SimulationReport is always returned.
        """
        t0 = time.monotonic()
        adoption_reports: list[AdoptionReport] = []

        for ed in prediction_report.emerging_directions:
            rag_context = await get_agent_context(
                direction=ed.direction,
                topic_context=topic_context,
                db=db,
                top_k=self._rag_top_k,
                min_score=self._rag_min_score,
            )
            try:
                adoption = await run_direction_simulation(
                    direction=ed.direction,
                    topic_context=topic_context,
                    rag_context=rag_context,
                    max_rounds=self._max_rounds,
                )
                adoption_reports.append(adoption)
                log.info(
                    "simulation_direction_complete",
                    direction=ed.direction[:80],
                    consensus=adoption.final_consensus,
                    verdict=adoption.adoption_verdict,
                )
            except Exception as exc:
                log.warning(
                    "simulation_direction_failed",
                    direction=ed.direction[:80],
                    error=str(exc),
                )

        duration = time.monotonic() - t0

        confidences = [r.final_consensus for r in adoption_reports]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        if avg_confidence >= 0.7:
            overall = "high"
        elif avg_confidence >= 0.4:
            overall = "medium"
        else:
            overall = "low"

        return SimulationReport(
            topic_context=topic_context,
            prediction_report_id=prediction_report_id,  # type: ignore[arg-type]
            adoption_reports=adoption_reports,
            overall_simulation_confidence=overall,
            model_name=settings.ollama_model,
            generated_at=datetime.now(UTC),
            duration_seconds=round(duration, 2),
        )
