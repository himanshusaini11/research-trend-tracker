"""Mark a prediction report as validated with optional notes.

Usage:
    uv run python scripts/validate_prediction.py \\
        --report-id <uuid> \\
        --notes "Predicted attention mechanism convergence — correct. Missed Mamba/SSM rise." \\
        --accurate partial
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.models import PredictionReportRow

_ACCURATE_CHOICES = ("yes", "no", "partial")


async def _run(report_id: uuid.UUID, notes: str, accurate: str) -> None:
    async with AsyncSessionLocal() as session:
        # Verify the report exists
        row = (
            await session.execute(
                select(PredictionReportRow).where(PredictionReportRow.id == report_id)
            )
        ).scalars().first()

        if row is None:
            print(f"Error: no report found with id={report_id}")
            sys.exit(1)

        validation_notes = f"[{accurate.upper()}] {notes}"

        await session.execute(
            update(PredictionReportRow)
            .where(PredictionReportRow.id == report_id)
            .values(is_validated=True, validation_notes=validation_notes)
        )
        await session.commit()

    print(f"Report {report_id} marked as validated.")
    print(f"  accurate:          {accurate}")
    print(f"  validation_notes:  {validation_notes}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a prediction report")
    parser.add_argument("--report-id", required=True, help="UUID of the prediction report")
    parser.add_argument("--notes", required=True, help="Free-text validation notes")
    parser.add_argument(
        "--accurate",
        choices=_ACCURATE_CHOICES,
        required=True,
        help="Accuracy assessment: yes / no / partial",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    try:
        report_id = uuid.UUID(args.report_id)
    except ValueError:
        print(f"Error: '{args.report_id}' is not a valid UUID")
        sys.exit(1)

    asyncio.run(_run(report_id, args.notes, args.accurate))
