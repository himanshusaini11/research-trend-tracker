from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import any_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.exceptions import NotFoundError
from app.core.models import Paper
from app.core.rate_limiter import RateLimiter

router = APIRouter(tags=["papers"])


def _paper_dict(p: Paper) -> dict[str, Any]:
    return {
        "arxiv_id": p.arxiv_id,
        "title": p.title,
        "abstract": p.abstract,
        "authors": p.authors,
        "categories": p.categories,
        "published_at": p.published_at.isoformat(),
        "ingested_at": p.ingested_at.isoformat(),
    }


@router.get("")
async def list_papers(
    category: str,
    days_back: Annotated[int, Query(ge=1, le=90)] = 7,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[dict[str, Any]]:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    since = datetime.now(UTC) - timedelta(days=days_back)
    stmt = (
        select(Paper)
        .where(
            category == any_(Paper.categories),
            Paper.published_at >= since,
        )
        .order_by(Paper.published_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_paper_dict(p) for p in rows]


@router.get("/count")
async def count_papers(
    category: str,
    days_back: Annotated[int, Query(ge=1, le=90)] = 7,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict[str, int]:
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    since = datetime.now(UTC) - timedelta(days=days_back)
    stmt = (
        select(func.count())
        .select_from(Paper)
        .where(
            category == any_(Paper.categories),
            Paper.published_at >= since,
        )
    )
    count = (await db.execute(stmt)).scalar_one()
    return {"count": count}


@router.get("/{arxiv_id}")
async def get_paper(
    arxiv_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    stmt = select(Paper).where(Paper.arxiv_id == arxiv_id)
    paper = (await db.execute(stmt)).scalar_one_or_none()
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Paper '{arxiv_id}' not found")
    return _paper_dict(paper)
