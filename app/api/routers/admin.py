"""Admin router — user management and system metrics. Requires is_admin=true in JWT."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.models import KeywordCount, Paper, PredictionReportRow, TrendScore, User

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Admin guard dependency
# ---------------------------------------------------------------------------

async def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserRow(BaseModel):
    id: str
    email: str
    is_admin: bool
    created_at: datetime
    last_login: datetime | None


class AdminStats(BaseModel):
    total_users: int
    admin_users: int
    active_users_7d: int        # logged in within last 7 days
    total_papers: int
    processed_papers: int       # graph_processed_at IS NOT NULL
    total_keywords: int         # distinct keywords in keyword_counts
    total_trend_scores: int
    last_pipeline_run: datetime | None  # most recent prediction_reports.generated_at


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserRow])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> list[UserRow]:
    """Return all registered users ordered by registration date."""
    rows = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return [
        UserRow(
            id=str(u.id),
            email=u.email,
            is_admin=u.is_admin,
            created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in rows
    ]


@router.get("/stats", response_model=AdminStats)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> AdminStats:
    """Return system-wide metrics for the admin dashboard."""
    cutoff_7d = datetime.now(UTC) - timedelta(days=7)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    admin_users = (
        await db.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
    ).scalar_one()

    active_users_7d = (
        await db.execute(
            select(func.count()).select_from(User).where(User.last_login >= cutoff_7d)
        )
    ).scalar_one()

    total_papers = (await db.execute(select(func.count()).select_from(Paper))).scalar_one()

    processed_papers = (
        await db.execute(
            select(func.count()).select_from(Paper).where(Paper.graph_processed_at.isnot(None))
        )
    ).scalar_one()

    total_keywords = (
        await db.execute(select(func.count(func.distinct(KeywordCount.keyword))))
    ).scalar_one()

    total_trend_scores = (
        await db.execute(select(func.count()).select_from(TrendScore))
    ).scalar_one()

    last_pipeline_run = (
        await db.execute(select(func.max(PredictionReportRow.generated_at)))
    ).scalar_one()

    return AdminStats(
        total_users=total_users,
        admin_users=admin_users,
        active_users_7d=active_users_7d,
        total_papers=total_papers,
        processed_papers=processed_papers,
        total_keywords=total_keywords,
        total_trend_scores=total_trend_scores,
        last_pipeline_run=last_pipeline_run,
    )


@router.patch("/users/{user_id}/toggle-admin", response_model=UserRow)
async def toggle_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: dict = Depends(require_admin),
) -> UserRow:
    """Promote or demote a user's admin status."""
    if str(current_admin.get("sub")) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin status",
        )
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_admin = not user.is_admin
    await db.flush()
    return UserRow(
        id=str(user.id),
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login,
    )
