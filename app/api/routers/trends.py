from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.aggregator import TrendAggregator
from app.analytics.schemas import AnalyticsResult
from app.analytics.trend_scorer import TrendScorer
from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.rate_limiter import RateLimiter

router = APIRouter(tags=["trends"])


@router.get("")
async def list_trends(
    category: str,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
    top_n: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[dict[str, Any]]:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    aggregator = TrendAggregator(db)
    trend_windows = await aggregator.get_trending_keywords(
        category=category,
        window_days=window_days,
        top_n=top_n,
    )
    return [tw.model_dump() for tw in trend_windows]


@router.get("/summary")
async def trends_summary(
    category: str,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    scorer = TrendScorer(db)
    trend_summaries = await scorer.get_top_trends(category=category)

    result = AnalyticsResult(
        category=category,
        window_days=window_days,
        trends=trend_summaries,
        generated_at=datetime.now(UTC),
    )
    return result.model_dump()
