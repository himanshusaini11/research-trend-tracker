"""Build CO_OCCURS_WITH edges for all papers in the AGE graph.

Iterates all papers with MENTIONS edges and calls build_concept_cooccurrence()
per paper in batches. Safe to re-run — AGE MERGE is idempotent.

Usage:
    uv run python scripts/build_cooccurrence.py
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.relation_builder import RelationBuilder

log = get_logger(__name__)

_BATCH_SIZE = 500


async def main() -> None:
    # Load all arxiv_ids (only need the ID, not the full Paper object)
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Paper.arxiv_id))).scalars().all()
    arxiv_ids = list(rows)
    total = len(arxiv_ids)
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
