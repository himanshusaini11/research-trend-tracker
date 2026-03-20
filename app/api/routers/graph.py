"""Graph router — exposes graph analysis signals via REST."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.graph.graph_analyzer import GraphAnalyzer
from app.graph.schemas import ConceptSignal

router = APIRouter(tags=["graph"])


@router.get("/top-concepts", response_model=list[ConceptSignal])
async def top_concepts(
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[ConceptSignal]:
    """Return top concepts ranked by composite_score (centrality + velocity)."""
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    analyzer = GraphAnalyzer(
        top_n=settings.graph_top_n_concepts,
        k_samples=settings.graph_centrality_k_samples,
    )
    return await analyzer.analyze(db)
