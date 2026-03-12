from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array as pg_array

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.models import Paper
from app.analytics.aggregator import TrendAggregator
from app.summarizer.chain import TrendSummarizerChain
from app.mcp_server.server import mcp


@mcp.tool()
async def get_trends(
    category: str,
    window_days: int = 7,
    top_n: int = 10,
) -> dict:
    """Return the top trending keywords for an arXiv category over a time window."""
    async with AsyncSessionLocal() as session:
        aggregator = TrendAggregator(session)
        trend_windows = await aggregator.get_trending_keywords(
            category=category,
            window_days=window_days,
            top_n=top_n,
        )

    return {
        "category": category,
        "window_days": window_days,
        "trends": [
            {"keyword": tw.keyword, "count": tw.count}
            for tw in trend_windows
        ],
    }


@mcp.tool()
async def get_top_papers(
    category: str,
    days_back: int = 7,
    limit: int = 10,
) -> dict:
    """Return the most recently published papers for an arXiv category."""
    since = datetime.now(UTC) - timedelta(days=days_back)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Paper)
            .where(
                Paper.categories.contains(pg_array([category])),
                Paper.published_at >= since,
            )
            .order_by(Paper.published_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()

    return {
        "category": category,
        "days_back": days_back,
        "papers": [
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "published_at": p.published_at.isoformat(),
            }
            for p in rows
        ],
    }


@mcp.tool()
async def summarize_week(
    category: str,
    window_days: int = 7,
) -> dict:
    """Summarize the dominant research themes for a category using an LLM."""
    async with AsyncSessionLocal() as session:
        aggregator = TrendAggregator(session)
        trend_windows = await aggregator.get_trending_keywords(
            category=category,
            window_days=window_days,
            top_n=10,
        )

    keywords = [tw.keyword for tw in trend_windows]

    chain = TrendSummarizerChain(
        ollama_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout=settings.ollama_request_timeout_seconds,
    )
    result = await chain.summarize(
        category=category,
        window_days=window_days,
        keywords=keywords,
    )

    return {
        "category": result.category,
        "summary": result.summary,
        "keywords_covered": result.keywords_covered,
        "model_used": result.model_used,
        "generated_at": result.generated_at.isoformat(),
    }
