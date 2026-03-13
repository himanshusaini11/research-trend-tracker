from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.trend_scorer import TrendScorer
from app.core.models import KeywordCount, TrendScore


def _add_keyword_count(session: AsyncSession, keyword: str, category: str, count: int = 5) -> None:
    session.add(
        KeywordCount(
            keyword=keyword,
            category=category,
            count=count,
            window_date=datetime.now(UTC),
        )
    )


async def test_score_and_persist_returns_count(test_db: AsyncSession) -> None:
    for kw in ["transformer", "attention", "neural"]:
        _add_keyword_count(test_db, kw, "cs.AI")
    await test_db.flush()

    scorer = TrendScorer(test_db)
    count = await scorer.score_and_persist("cs.AI", date.today())
    assert count > 0


async def test_get_top_trends_empty_db(test_db: AsyncSession) -> None:
    scorer = TrendScorer(test_db)
    trends = await scorer.get_top_trends("cs.AI")
    assert trends == []


async def test_upsert_idempotent(test_db: AsyncSession) -> None:
    _add_keyword_count(test_db, "neural", "cs.AI")
    await test_db.flush()

    window_date = date.today()
    scorer = TrendScorer(test_db)

    await scorer.score_and_persist("cs.AI", window_date)
    await test_db.flush()
    await scorer.score_and_persist("cs.AI", window_date)
    await test_db.flush()

    window_start = datetime(window_date.year, window_date.month, window_date.day, tzinfo=UTC)
    row_count = await test_db.scalar(
        select(func.count()).where(
            TrendScore.keyword == "neural",
            TrendScore.category == "cs.AI",
            TrendScore.window_start == window_start,
        )
    )
    assert row_count == 1
