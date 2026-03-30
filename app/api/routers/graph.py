"""Graph router — exposes graph analysis signals and prediction reports via REST."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.config import settings
from app.core.logger import get_logger
from app.core.models import Paper, PredictionReportRow
from app.core.rate_limiter import RateLimiter
from app.graph.graph_analyzer import GraphAnalyzer
from app.graph.prediction_synthesizer import PredictionSynthesizer
from app.graph.report_archive import ReportArchive
from app.graph.schemas import ArchivedReport, ConceptSignal, PredictionReport
from app.services import rag
from app.services.rag import PaperResult

log = get_logger(__name__)

router = APIRouter(tags=["graph"])


class GenerateRequest(BaseModel):
    topic_context: str = "AI/ML research"


class GenerateResponse(BaseModel):
    id: str
    report: PredictionReport
    sources: list[PaperResult] = []


class GraphStats(BaseModel):
    papers_processed: int
    last_run: str | None


@router.get("/top-concepts", response_model=list[ConceptSignal])
async def top_concepts(
    paper_from: str | None = Query(default=None, description="ISO date — filter to papers published on or after this date"),
    paper_to:   str | None = Query(default=None, description="ISO date — filter to papers published before this date"),
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[ConceptSignal]:
    """Return top concepts ranked by composite_score (centrality + velocity).

    When paper_from / paper_to are provided, results are scoped to concepts
    extracted from papers in that date range (e.g. to compare model quality).
    """
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    analyzer = GraphAnalyzer(
        top_n=settings.graph_top_n_concepts,
        k_samples=settings.graph_centrality_k_samples,
    )

    if paper_from and paper_to:
        return await analyzer.read_signals_for_date_range(db, paper_from, paper_to)

    return await analyzer.read_signals(db)


@router.get("/concepts", response_model=list[ConceptSignal])
async def get_concepts_page(
    limit:  Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)]          = 0,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[ConceptSignal]:
    """Paginated concept list ranked by composite_score — for incremental graph loading.

    Use offset to fetch only the delta when the user expands the node count slider.
    """
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    analyzer = GraphAnalyzer(
        top_n=settings.graph_top_n_concepts,
        k_samples=settings.graph_centrality_k_samples,
    )
    return await analyzer.read_signals_page(db, limit=limit, offset=offset)


@router.get("/stats", response_model=GraphStats)
async def graph_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> GraphStats:
    """Return graph-level stats: papers processed and last pipeline run timestamp."""
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    papers_processed: int = (
        await db.scalar(
            select(func.count()).select_from(Paper).where(Paper.graph_processed_at.is_not(None))
        )
    ) or 0

    last_run_dt = await db.scalar(
        select(PredictionReportRow.generated_at).order_by(PredictionReportRow.generated_at.desc()).limit(1)
    )
    last_run = last_run_dt.isoformat() if last_run_dt else None

    return GraphStats(papers_processed=papers_processed, last_run=last_run)


@router.get("/predictions/latest", response_model=list[ArchivedReport])
async def get_latest_predictions(
    topic_context: str = "AI/ML research",
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[ArchivedReport]:
    """Return the most recent archived prediction reports for a topic."""
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    archive = ReportArchive()
    return await archive.get_latest(db, topic_context=topic_context, limit=limit)


@router.post("/predictions/generate", response_model=GenerateResponse)
async def generate_prediction(
    body: GenerateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> GenerateResponse:
    """On-demand prediction synthesis from the current graph state."""
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    analyzer = GraphAnalyzer(
        top_n=settings.graph_top_n_concepts,
        k_samples=settings.graph_centrality_k_samples,
    )
    signals = (await analyzer.read_signals(db))[: settings.predict_top_signals]

    retrieved = await rag.get_context_for_text(
        text_query=body.topic_context,
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
        db=db,
    )
    log.info(
        "prediction_rag_sources",
        count=len(retrieved),
        signals_count=len(signals),
        topic_context=body.topic_context,
    )

    synthesizer = PredictionSynthesizer(
        model=settings.ollama_predict_model,
        timeout=settings.ollama_predict_timeout_seconds,
    )
    report = await synthesizer.synthesize(
        signals, topic_context=body.topic_context, sources=retrieved
    )

    archive = ReportArchive()
    report_id = await archive.save(
        session=db,
        topic_context=body.topic_context,
        signals=signals,
        report=report,
        model_name=settings.ollama_predict_model,
    )

    return GenerateResponse(id=str(report_id), report=report, sources=retrieved)
