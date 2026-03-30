from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import get_sync_engine
from app.services.embedding import get_embeddings_batch

log = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.embed_papers.embed_unprocessed_papers", bind=True)
def embed_unprocessed_papers(
    self, limit: int | None = None
) -> dict[str, int]:  # type: ignore[override]
    """Embed abstracts of all papers not yet in paper_embeddings. Idempotent.

    Args:
        limit: If set, process at most N papers. Useful for dev testing on a small
               slice. None embeds all unembedded papers (production behaviour).
    """
    engine = get_sync_engine()

    limit_clause = "LIMIT :limit" if limit is not None else ""
    with Session(engine) as db:
        rows = db.execute(
            text(f"""
                SELECT id, abstract FROM papers
                WHERE id NOT IN (SELECT paper_id FROM paper_embeddings)
                ORDER BY id
                {limit_clause}
            """),
            {"limit": limit} if limit is not None else {},
        ).fetchall()

    if not rows:
        log.info("embed_papers_skip", reason="no unprocessed papers")
        return {"embedded": 0, "skipped": 0}

    total = len(rows)
    batch_size = settings.embed_batch_size
    log.info("embed_papers_start", total=total, batch_size=batch_size)

    embedded_count = 0
    skip_count = 0
    batches = [rows[i : i + batch_size] for i in range(0, total, batch_size)]

    with Session(engine) as db:
        for batch_idx, batch in enumerate(batches):
            paper_ids = [r[0] for r in batch]
            abstracts = [r[1] for r in batch]

            vectors = asyncio.run(get_embeddings_batch(abstracts))

            now = datetime.now(timezone.utc)
            inserts: list[dict] = []
            batch_skipped = 0
            for paper_id, vector in zip(paper_ids, vectors):
                if vector is None:
                    batch_skipped += 1
                    skip_count += 1
                    continue
                vec_str = "[" + ",".join(str(v) for v in vector) + "]"
                inserts.append(
                    {"paper_id": paper_id, "embedding": vec_str, "embedded_at": now}
                )
                embedded_count += 1

            if inserts:
                db.execute(
                    text("""
                        INSERT INTO paper_embeddings (paper_id, embedding, embedded_at)
                        VALUES (:paper_id, CAST(:embedding AS vector), :embedded_at)
                    """),
                    inserts,
                )
                db.commit()

            if batch_skipped:
                log.warning(
                    "embed_batch_items_skipped", batch=batch_idx, skipped=batch_skipped
                )

            if (batch_idx + 1) % 10 == 0:
                log.info(
                    "embed_papers_progress",
                    batches_done=batch_idx + 1,
                    total_batches=len(batches),
                    embedded_so_far=embedded_count,
                    total=total,
                )

    log.info("embed_papers_complete", embedded=embedded_count, skipped=skip_count)
    return {"embedded": embedded_count, "skipped": skip_count}
