"""Bridge between the simulation engine and the existing RAG service."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.services.rag import PaperResult, get_context_for_text

log = get_logger(__name__)


async def get_agent_context(
    direction: str,
    topic_context: str,
    db: AsyncSession,
    top_k: int = 5,
    min_score: float = 0.6,
) -> list[PaperResult]:
    """Retrieve RAG-grounded papers for a single emerging direction.

    Combines direction text with topic_context for a richer semantic query.
    Uses min_score=0.6 (lower than the app default of 0.7) to cast a broader
    net for simulation context.  Falls back to [] on any error so the
    simulation is never blocked by an embedding / DB issue.
    """
    query = f"{topic_context}: {direction}"
    try:
        results = await get_context_for_text(
            text_query=query,
            top_k=top_k,
            min_score=min_score,
            db=db,
        )
        log.info(
            "simulation_grounding",
            direction=direction[:80],
            results=len(results),
        )
        return results
    except Exception as exc:
        log.warning(
            "simulation_grounding_failed",
            direction=direction[:80],
            error=str(exc),
        )
        return []
