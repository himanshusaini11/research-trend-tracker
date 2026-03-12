from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount
from app.analytics.schemas import TrendWindow


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    """Ordinary least squares slope without numpy."""
    n = len(xs)
    if n < 2:
        return 0.0
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sum_xx - sum_x * sum_x
    return 0.0 if denom == 0 else (n * sum_xy - sum_x * sum_y) / denom


class TrendAggregator:
    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def get_trending_keywords(
        self,
        category: str,
        window_days: int = 7,
        top_n: int = 20,
    ) -> list[TrendWindow]:
        since = datetime.now(UTC) - timedelta(days=window_days)

        stmt = (
            select(
                KeywordCount.keyword,
                KeywordCount.category,
                KeywordCount.window_date,
                func.sum(KeywordCount.count).label("total"),
            )
            .where(
                KeywordCount.category == category,
                KeywordCount.window_date >= since,
            )
            .group_by(
                KeywordCount.keyword,
                KeywordCount.category,
                KeywordCount.window_date,
            )
            .order_by(func.sum(KeywordCount.count).desc())
            .limit(top_n)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            TrendWindow(
                keyword=row.keyword,
                category=row.category,
                window_date=row.window_date.date(),
                count=int(row.total),
                rank=i + 1,
            )
            for i, row in enumerate(rows)
        ]

    async def get_keyword_velocity(
        self,
        keyword: str,
        category: str,
        window_days: int = 30,
    ) -> float:
        since = datetime.now(UTC) - timedelta(days=window_days)

        stmt = (
            select(KeywordCount.window_date, func.sum(KeywordCount.count).label("total"))
            .where(
                KeywordCount.keyword == keyword,
                KeywordCount.category == category,
                KeywordCount.window_date >= since,
            )
            .group_by(KeywordCount.window_date)
            .order_by(KeywordCount.window_date)
        )

        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return 0.0

        xs = [float(i) for i in range(len(rows))]
        ys = [float(row.total) for row in rows]
        return _linear_slope(xs, ys)
