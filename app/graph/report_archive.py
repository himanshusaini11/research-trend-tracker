"""Report archive — persists and retrieves PredictionReport rows from Postgres."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.models import PredictionReportRow
from app.graph.schemas import ArchivedReport, ConceptSignal, PredictionReport

log = get_logger(__name__)


class ReportArchive:
    """Saves and retrieves prediction reports from the prediction_reports table."""

    async def save(
        self,
        session: AsyncSession,
        topic_context: str,
        signals: list[ConceptSignal],
        report: PredictionReport,
        model_name: str,
    ) -> uuid.UUID:
        """Persist a prediction report and return its UUID."""
        row = PredictionReportRow(
            topic_context=topic_context,
            signals_snapshot=[s.model_dump() for s in signals],
            report=report.model_dump(),
            model_name=model_name,
            generated_at=datetime.now(UTC),
            is_validated=False,
            validation_notes=None,
        )
        session.add(row)
        await session.flush()  # populate server-generated id

        log.info(
            "report_archive_saved",
            report_id=str(row.id),
            topic_context=topic_context,
            model_name=model_name,
        )
        return row.id

    async def get_latest(
        self,
        session: AsyncSession,
        topic_context: str,
        limit: int = 10,
    ) -> list[ArchivedReport]:
        """Return the most recent reports for a topic_context, newest first."""
        rows = (
            await session.execute(
                select(PredictionReportRow)
                .where(PredictionReportRow.topic_context == topic_context)
                .order_by(desc(PredictionReportRow.generated_at))
                .limit(limit)
            )
        ).scalars().all()

        return [
            ArchivedReport(
                id=r.id,
                topic_context=r.topic_context,
                report=r.report,
                model_name=r.model_name,
                generated_at=r.generated_at,
                is_validated=r.is_validated,
            )
            for r in rows
        ]
