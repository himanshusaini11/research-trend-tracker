from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import any_, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.models import BridgeNodeScore, Paper, PredictionReportRow, SimulationResultRow, VelocityScore
from app.analytics.aggregator import TrendAggregator
from app.summarizer.chain import TrendSummarizerChain
from app.mcp_server.server import mcp


def _normalize_list(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


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
                category == any_(Paper.categories),  # type: ignore[arg-type]  # SQLAlchemy any_() returns ColumnElement at runtime
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


@mcp.tool()
async def query_knowledge_graph(
    top_n: int = 20,
    trend_filter: str = "all",
) -> list[dict]:
    """
    Returns the top N concepts from the knowledge graph with their
    centrality scores, velocity, trend classification, and composite score.
    Optionally filter by trend: 'accelerating', 'decelerating', 'stable', 'all'.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(BridgeNodeScore, VelocityScore).join(
            VelocityScore,
            BridgeNodeScore.concept_name == VelocityScore.concept_name,
        )
        if trend_filter != "all":
            stmt = stmt.where(VelocityScore.trend == trend_filter)
        rows = (await session.execute(stmt)).all()

    if not rows:
        return []

    centrality_vals = [b.centrality_score for b, _ in rows]
    velocity_vals = [v.velocity for _, v in rows]
    norm_c = _normalize_list(centrality_vals)
    norm_v = _normalize_list(velocity_vals)

    results: list[dict] = []
    for (b, v), nc, nv in sorted(
        zip(rows, norm_c, norm_v),
        key=lambda t: 0.6 * t[1] + 0.4 * t[2],
        reverse=True,
    )[:top_n]:
        composite = round(0.6 * nc + 0.4 * nv, 6)
        results.append(
            {
                "concept_name": b.concept_name,
                "centrality_score": b.centrality_score,
                "velocity": v.velocity,
                "acceleration": v.acceleration,
                "trend": v.trend,
                "composite_score": composite,
            }
        )

    return results


@mcp.tool()
async def get_prediction_report(
    topic_context: str = "AI/ML research",
) -> dict:
    """
    Returns the most recent prediction report for the given topic context.
    Includes emerging directions, unexplored gaps, predicted convergences,
    and overall confidence level.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(PredictionReportRow)
            .where(PredictionReportRow.topic_context == topic_context)
            .order_by(PredictionReportRow.generated_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalars().first()

    if row is None:
        return {}

    return {
        "id": str(row.id),
        "topic_context": row.topic_context,
        "report": row.report,
        "model_name": row.model_name,
        "generated_at": row.generated_at.isoformat(),
        "is_validated": row.is_validated,
    }


@mcp.tool()
async def run_research_simulation(
    topic_context: str = "AI/ML research",
    max_rounds: int = 3,
) -> dict:
    """
    Dispatch an ARIS multi-agent adoption simulation for the most recent
    prediction report matching the given topic context.
    Three personas (researcher, venture_capitalist, policy_maker) deliberate
    over each emerging direction for up to max_rounds rounds.
    Returns a Celery job_id — poll get_simulation_report for results.
    """
    from app.tasks.run_simulation import run_simulation_task

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(PredictionReportRow)
                .where(PredictionReportRow.topic_context == topic_context)
                .order_by(PredictionReportRow.generated_at.desc())
                .limit(1)
            )
        ).scalars().first()

    if row is None:
        return {"error": f"No prediction report found for topic: {topic_context!r}"}

    task = run_simulation_task.delay(
        prediction_report_dict=row.report,
        topic_context=topic_context,
        prediction_report_id=str(row.id),
        max_rounds=max_rounds,
    )
    return {"job_id": task.id, "status": "queued", "topic_context": topic_context}


@mcp.tool()
async def get_simulation_report(
    topic_context: str = "AI/ML research",
) -> dict:
    """
    Returns the most recent completed ARIS simulation result for the given
    topic context. Includes per-direction adoption verdicts, consensus scores,
    shared concerns (death valleys), and overall simulation confidence.
    Returns an empty dict if no simulation has been run yet.
    """
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(SimulationResultRow)
                .where(SimulationResultRow.topic_context == topic_context)
                .order_by(SimulationResultRow.generated_at.desc())
                .limit(1)
            )
        ).scalars().first()

    if row is None:
        return {}

    return {
        "id": str(row.id),
        "topic_context": row.topic_context,
        "results": row.results,
        "model_name": row.model_name,
        "generated_at": row.generated_at.isoformat(),
        "duration_seconds": row.duration_seconds,
    }
