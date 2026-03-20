from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount, TrendScore
from app.analytics.aggregator import TrendAggregator
from app.analytics.schemas import TrendSummary, TrendWindow

_RISING_THRESHOLD = 0.5
_FALLING_THRESHOLD = -0.5


def _direction(velocity: float) -> str:
    if velocity > _RISING_THRESHOLD:
        return "rising"
    if velocity < _FALLING_THRESHOLD:
        return "falling"
    return "stable"


class TrendScorer:
    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session
        self._aggregator = TrendAggregator(db_session)

    async def score_and_persist(self, category: str, window_date: date) -> int:
        """Compute and upsert TrendScore rows for all top keywords on window_date."""
        trending = await self._aggregator.get_trending_keywords(
            category=category, window_days=7, top_n=20
        )
        if not trending:
            return 0

        window_start = datetime(
            window_date.year, window_date.month, window_date.day, tzinfo=UTC
        )
        window_end = window_start + timedelta(days=1)

        rows = []
        for tw in trending:
            velocity = await self._aggregator.get_keyword_velocity(
                keyword=tw.keyword, category=category
            )
            rows.append(
                {
                    "keyword": tw.keyword,
                    "category": category,
                    "score": velocity,
                    "trend_direction": _direction(velocity),
                    "window_start": window_start,
                    "window_end": window_end,
                }
            )

        stmt = (
            insert(TrendScore)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["keyword", "category", "window_start"],
                set_={
                    "score": insert(TrendScore).excluded.score,
                    "trend_direction": insert(TrendScore).excluded.trend_direction,
                    "window_end": insert(TrendScore).excluded.window_end,
                },
            )
        )
        await self._session.execute(stmt)
        return len(rows)

    async def get_top_trends(
        self, category: str, limit: int = 10
    ) -> list[TrendSummary]:
        """Return enriched TrendSummary list from latest trend_scores + keyword_counts."""
        # Latest score per keyword: subquery selects max window_start per keyword/category
        subq = (
            select(
                TrendScore.keyword,
                TrendScore.score,
            )
            .where(TrendScore.category == category)
            .order_by(TrendScore.score.desc())
            .limit(limit)
            .subquery()
        )

        score_rows = (
            await self._session.execute(select(subq))
        ).all()

        if not score_rows:
            return []

        keywords = [r.keyword for r in score_rows]
        velocities = {r.keyword: r.score for r in score_rows}

        # Fetch per-day counts for all keywords in one query
        kc_stmt = (
            select(
                KeywordCount.keyword,
                KeywordCount.category,
                KeywordCount.window_date,
                KeywordCount.count,
            )
            .where(
                KeywordCount.keyword.in_(keywords),
                KeywordCount.category == category,
            )
            .order_by(KeywordCount.keyword, KeywordCount.window_date)
        )
        kc_rows = (await self._session.execute(kc_stmt)).all()

        # Group by keyword
        windows_by_kw: dict[str, list[TrendWindow]] = {kw: [] for kw in keywords}
        totals: dict[str, int] = {kw: 0 for kw in keywords}
        for row in kc_rows:
            if row.keyword in windows_by_kw:
                windows_by_kw[row.keyword].append(
                    TrendWindow(
                        keyword=row.keyword,
                        category=row.category,
                        window_date=row.window_date.date(),
                        count=cast(int, row.count),  # Row named attr; mypy confuses with tuple.count()
                    )
                )
                totals[row.keyword] += cast(int, row.count)

        return [
            TrendSummary(
                keyword=kw,
                total_count=totals[kw],
                window_counts=windows_by_kw[kw],
                velocity=velocities[kw],
            )
            for kw in keywords
        ]
