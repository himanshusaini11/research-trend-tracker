from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.aggregator import TrendAggregator
from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.rate_limiter import RateLimiter
from app.summarizer.chain import TrendSummarizerChain
from app.summarizer.schemas import SummarizeRequest, TrendSummaryOutput

router = APIRouter(tags=["summarize"])


@router.post("")
async def summarize(
    body: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    aggregator = TrendAggregator(db)
    trend_windows = await aggregator.get_trending_keywords(
        category=body.category,
        window_days=body.window_days,
        top_n=body.top_n,
    )
    keywords = [tw.keyword for tw in trend_windows]

    chain = TrendSummarizerChain(
        ollama_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout=settings.ollama_request_timeout_seconds,
    )
    try:
        result: TrendSummaryOutput = await chain.summarize(
            category=body.category,
            window_days=body.window_days,
            keywords=keywords,
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM error: {exc.message}",
        ) from exc

    return result.model_dump()
