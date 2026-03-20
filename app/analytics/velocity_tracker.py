"""Velocity tracker — computes citation-rate acceleration from keyword_counts
time series stored in TimescaleDB.

Lives in app/analytics/ (not app/graph/) because it queries Postgres/TimescaleDB,
not the AGE graph.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.models import VelocityScore
from app.graph.schemas import VelocityResult

log = get_logger(__name__)

_WEEKLY_COUNTS_SQL = """
SELECT
    date_trunc('week', window_date) AS week,
    SUM(count) AS weekly_count
FROM keyword_counts
WHERE keyword = :concept_name
GROUP BY week
ORDER BY week ASC;
"""

VelocityTrend = Literal["accelerating", "decelerating", "stable"]


def _classify_trend(velocities: list[float]) -> VelocityTrend:
    """Classify trend from the last two velocity values."""
    if len(velocities) < 2:
        return "stable"
    v_prev, v_last = velocities[-2], velocities[-1]
    if v_prev > 0 and v_last > 0:
        return "accelerating"
    if v_prev < 0 and v_last < 0:
        return "decelerating"
    return "stable"


class VelocityTracker:
    """Computes week-over-week velocity and acceleration for concept keywords.

    Queries keyword_counts for each concept, computes first and second
    derivative of the weekly count, and stores results in velocity_scores.
    """

    async def compute(
        self,
        session: AsyncSession,
        concept_names: list[str],
    ) -> list[VelocityResult]:
        """Compute velocity and acceleration for each concept.

        Returns one VelocityResult per concept. Concepts with fewer than
        2 weeks of data get velocity=0, acceleration=0, trend='stable'.
        Results are upserted into velocity_scores.
        """
        results: list[VelocityResult] = []
        computed_at = datetime.now(UTC)
        rows_to_upsert = []

        for concept_name in concept_names:
            weekly_rows = (
                await session.execute(
                    text(_WEEKLY_COUNTS_SQL).bindparams(concept_name=concept_name)
                )
            ).all()

            counts: list[float] = [float(r[1]) for r in weekly_rows]
            weeks_of_data = len(counts)

            if weeks_of_data < 2:
                velocity = 0.0
                acceleration = 0.0
                trend: VelocityTrend = "stable"
            else:
                velocities = [counts[i] - counts[i - 1] for i in range(1, len(counts))]
                velocity = velocities[-1]

                if len(velocities) < 2:
                    acceleration = 0.0
                else:
                    accelerations = [
                        velocities[i] - velocities[i - 1]
                        for i in range(1, len(velocities))
                    ]
                    acceleration = accelerations[-1]

                trend = _classify_trend(velocities)

            result = VelocityResult(
                concept_name=concept_name,
                velocity=velocity,
                acceleration=acceleration,
                trend=trend,
                weeks_of_data=weeks_of_data,
            )
            results.append(result)
            rows_to_upsert.append(
                {
                    "concept_name": concept_name,
                    "velocity": velocity,
                    "acceleration": acceleration,
                    "trend": trend,
                    "weeks_of_data": weeks_of_data,
                    "computed_at": computed_at,
                }
            )

        if rows_to_upsert:
            stmt = pg_insert(VelocityScore).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_update(
                index_elements=["concept_name"],
                set_={
                    "velocity": stmt.excluded.velocity,
                    "acceleration": stmt.excluded.acceleration,
                    "trend": stmt.excluded.trend,
                    "weeks_of_data": stmt.excluded.weeks_of_data,
                    "computed_at": stmt.excluded.computed_at,
                },
            )
            await session.execute(stmt)

        log.info("velocity_tracker_done", concepts_computed=len(results))
        return results
