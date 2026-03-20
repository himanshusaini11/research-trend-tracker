"""Graph router — exposes graph analysis signals and prediction reports via REST."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rate_limiter
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.graph.graph_analyzer import GraphAnalyzer
from app.graph.prediction_synthesizer import PredictionSynthesizer
from app.graph.report_archive import ReportArchive
from app.graph.schemas import ArchivedReport, ConceptSignal, PredictionReport

router = APIRouter(tags=["graph"])


class GenerateRequest(BaseModel):
    topic_context: str = "AI/ML research"


class GenerateResponse(BaseModel):
    id: str
    report: PredictionReport


@router.get("/top-concepts", response_model=list[ConceptSignal])
async def top_concepts(
    db: AsyncSession = Depends(get_db),
    _user: dict[str, Any] = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[ConceptSignal]:
    """Return top concepts ranked by composite_score (centrality + velocity)."""
    if not await rate_limiter.is_allowed(_user.get("sub", "anonymous")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    analyzer = GraphAnalyzer(
        top_n=settings.graph_top_n_concepts,
        k_samples=settings.graph_centrality_k_samples,
    )
    return await analyzer.analyze(db)


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
    signals = await analyzer.analyze(db)

    synthesizer = PredictionSynthesizer()
    report = await synthesizer.synthesize(signals, topic_context=body.topic_context)

    archive = ReportArchive()
    report_id = await archive.save(
        session=db,
        topic_context=body.topic_context,
        signals=signals,
        report=report,
        model_name=settings.ollama_model,
    )

    return GenerateResponse(id=str(report_id), report=report)
