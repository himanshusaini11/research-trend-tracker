"""Build CO_OCCURS_WITH edges for papers in the AGE graph.

Only processes papers where cooccurrence_processed_at IS NULL, so it is safe
and cheap to re-run — it will only touch papers that haven't been covered yet
(e.g. new papers added since the last run), not the full corpus each time.

Usage:
    uv run python scripts/build_cooccurrence.py
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.relation_builder import RelationBuilder

log = get_logger(__name__)

_BATCH_SIZE = 500


async def main() -> None:
    # Only load papers not yet covered (idempotent, same pattern as graph_processed_at)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Paper.arxiv_id).where(Paper.cooccurrence_processed_at.is_(None))
            )
        ).scalars().all()
    arxiv_ids = list(rows)
    total = len(arxiv_ids)
    if total == 0:
        print("No unprocessed papers found — CO_OCCURS_WITH is already up to date.")
        return
    print(f"Building CO_OCCURS_WITH edges for {total:,} papers (batch size {_BATCH_SIZE})…")

    done = 0
    start = time.monotonic()

    for batch_start in range(0, total, _BATCH_SIZE):
        batch = arxiv_ids[batch_start: batch_start + _BATCH_SIZE]
        async with AsyncSessionLocal() as session:
            builder = RelationBuilder(session)
            await builder.setup()
            for arxiv_id in batch:
                await builder.build_concept_cooccurrence(arxiv_id)
            await session.execute(
                update(Paper)
                .where(Paper.arxiv_id.in_(batch))
                .values(cooccurrence_processed_at=datetime.now(UTC))
            )
            await session.commit()

        done += len(batch)
        elapsed = time.monotonic() - start
        rate = done / elapsed
        remaining = (total - done) / rate / 60 if rate > 0 else 0
        print(
            f"  [{done:,} / {total:,}] ({done/total*100:.1f}%) — "
            f"{elapsed/60:.1f} min elapsed, ~{remaining:.0f} min remaining"
        )

    print(f"\nDone. {done:,} papers processed in {(time.monotonic()-start)/60:.1f} min.")

    # Verify
    async with AsyncSessionLocal() as session:
        conn = await session.connection()
        await conn.exec_driver_sql("LOAD 'age'")
        await conn.exec_driver_sql("SET search_path = ag_catalog, \"$user\", public")
        r = await conn.exec_driver_sql(
            "SELECT * FROM cypher('research_graph', $$ "
            "MATCH ()-[e:CO_OCCURS_WITH]->() RETURN count(e) AS cnt "
            "$$) AS (cnt agtype)"
        )
        rows = r.all()
        print(f"CO_OCCURS_WITH edges in graph: {rows[0][0] if rows else 0}")


if __name__ == "__main__":
    asyncio.run(main())
