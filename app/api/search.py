from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.services.rag import PaperResult, get_context_for_text

router = APIRouter(prefix="/api/v1", tags=["search"])


class SearchResponse(BaseModel):
    results: list[PaperResult]
    query: str
    total: int


@router.get("/search", response_model=SearchResponse)
async def search_papers(
    q: str,
    top_k: Annotated[int, Query(ge=1, le=20)] = 10,
    min_score: Annotated[float, Query(ge=0.0, le=1.0)] = settings.rag_min_score,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> SearchResponse:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )
    results = await get_context_for_text(
        text_query=q, top_k=top_k, min_score=min_score, db=db
    )
    return SearchResponse(results=results, query=q, total=len(results))
