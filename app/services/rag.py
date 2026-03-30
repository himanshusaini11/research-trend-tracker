from __future__ import annotations

from datetime import datetime

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import embedding as emb

log = structlog.get_logger(__name__)


class PaperResult(BaseModel):
    paper_id: int
    arxiv_id: str
    title: str
    abstract_snippet: str
    score: float
    published_at: datetime


async def search_similar(
    embedding: list[float],
    top_k: int = 5,
    min_score: float = 0.7,
    db: AsyncSession = ...,  # type: ignore[assignment]
) -> list[PaperResult]:
    """Find papers whose embeddings are most similar to the query embedding."""
    query_vec = "[" + ",".join(str(v) for v in embedding) + "]"
    sql = text("""
        SELECT
            pe.paper_id,
            p.arxiv_id,
            p.title,
            LEFT(p.abstract, 300)                                    AS abstract_snippet,
            1 - (pe.embedding <=> CAST(:query_vec AS vector))        AS score,
            p.published_at
        FROM paper_embeddings pe
        JOIN papers p ON p.id = pe.paper_id
        WHERE 1 - (pe.embedding <=> CAST(:query_vec AS vector)) >= :min_score
        ORDER BY score DESC
        LIMIT :top_k
    """)
    result = await db.execute(
        sql, {"query_vec": query_vec, "min_score": min_score, "top_k": top_k}
    )
    rows = result.mappings().all()
    return [PaperResult(**dict(row)) for row in rows]


async def get_context_for_text(
    text_query: str,
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[PaperResult]:
    """Embed text_query and return the most similar papers."""
    vector = await emb.get_embedding(text_query)
    results = await search_similar(vector, top_k=top_k, min_score=min_score, db=db)
    log.info(
        "rag_search",
        query=text_query[:100],
        result_count=len(results),
        top_k=top_k,
        min_score=min_score,
    )
    return results
