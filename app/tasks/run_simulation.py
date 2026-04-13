"""Celery task: run ARIS multi-agent simulation for a prediction report."""
from __future__ import annotations

import asyncio
import json

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_sync_engine
from app.graph.schemas import PredictionReport, SimulationReport
from app.simulation.runner import SimulationRunner

log = structlog.get_logger(__name__)


@celery_app.task(
    name="app.tasks.run_simulation.run_simulation_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_simulation_task(
    self,
    prediction_report_dict: dict,
    topic_context: str,
    prediction_report_id: str | None = None,
    max_rounds: int = 3,
) -> dict[str, object]:
    """Run multi-agent simulation and persist result to simulation_results table.

    Args:
        prediction_report_dict: PredictionReport serialised as a plain dict
            (JSON-safe — passed through Celery's Redis broker).
        topic_context: Human-readable framing for the simulation (e.g. "AI/ML research").
        prediction_report_id: UUID string of the source PredictionReportRow, or None
            for ad-hoc runs not linked to an archived report.
        max_rounds: Maximum deliberation rounds per direction (default 3).

    Returns:
        {"status": "complete", "directions": <int>}
    """
    prediction_report = PredictionReport.model_validate(prediction_report_dict)

    async def _run() -> SimulationReport:
        async with AsyncSessionLocal() as session:
            runner = SimulationRunner(max_rounds=max_rounds)
            return await runner.run(
                prediction_report=prediction_report,
                topic_context=topic_context,
                db=session,
                prediction_report_id=prediction_report_id,
            )

    try:
        sim_report = asyncio.run(_run())
    except Exception as exc:
        log.error(
            "run_simulation_task_failed",
            topic_context=topic_context,
            error=str(exc),
        )
        raise self.retry(exc=exc)

    # Persist with sync session — same pattern as embed_papers.py
    engine = get_sync_engine()
    with Session(engine) as db:
        db.execute(
            text("""
                INSERT INTO simulation_results
                    (prediction_report_id, topic_context, simulation_config,
                     results, model_name, generated_at, duration_seconds)
                VALUES
                    (:pred_id, :topic_context,
                     CAST(:config AS jsonb), CAST(:results AS jsonb),
                     :model_name, :generated_at, :duration)
            """),
            {
                "pred_id": prediction_report_id,
                "topic_context": topic_context,
                "config": json.dumps({"max_rounds": max_rounds}),
                "results": sim_report.model_dump_json(),
                "model_name": sim_report.model_name,
                "generated_at": sim_report.generated_at,
                "duration": sim_report.duration_seconds,
            },
        )
        db.commit()

    log.info(
        "run_simulation_task_complete",
        topic_context=topic_context,
        directions=len(sim_report.adoption_reports),
        overall_confidence=sim_report.overall_simulation_confidence,
        duration=sim_report.duration_seconds,
    )
    return {
        "status": "complete",
        "directions": len(sim_report.adoption_reports),
    }
