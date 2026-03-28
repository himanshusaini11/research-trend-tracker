"""User graph router — personal knowledge graph, velocity, and predictions."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.models import UserConcept, UserGraphEdge, UserPaper

router = APIRouter(tags=["user-graph"])


class GraphNode(BaseModel):
    id: str
    weight: float
    mention_count: int


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    weight: float


class UserGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: dict[str, int]


@router.get("", response_model=UserGraphResponse)
async def get_user_graph(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserGraphResponse:
    """Return the user's personal knowledge graph derived from uploaded papers."""
    if current_user.get("role") == "demo":
        raise HTTPException(status_code=403, detail="Demo accounts have no personal graph")

    user_uuid = uuid.UUID(current_user["sub"])

    # All concepts for this user
    concepts = (
        await db.execute(
            select(UserConcept).where(UserConcept.user_id == user_uuid)
        )
    ).scalars().all()

    if not concepts:
        return UserGraphResponse(nodes=[], edges=[], meta={"total_concepts": 0})

    # Aggregate weight and mention count per concept name
    concept_weights: Counter = Counter()
    concept_mentions: Counter = Counter()
    for c in concepts:
        concept_weights[c.concept] += c.weight
        concept_mentions[c.concept] += 1

    total_concepts = len(concept_weights)

    # Top N by aggregated weight
    top_concepts = {
        name: concept_weights[name]
        for name, _ in concept_weights.most_common(limit)
    }

    nodes = [
        GraphNode(
            id=name,
            weight=round(weight, 6),
            mention_count=concept_mentions[name],
        )
        for name, weight in top_concepts.items()
    ]

    # Edges — only between concepts in our top-N
    top_set = set(top_concepts.keys())
    raw_edges = (
        await db.execute(
            select(UserGraphEdge).where(UserGraphEdge.user_id == user_uuid)
        )
    ).scalars().all()

    seen: set[frozenset] = set()
    edges = []
    for e in raw_edges:
        key = frozenset({e.source_concept, e.target_concept})
        if e.source_concept in top_set and e.target_concept in top_set and key not in seen:
            seen.add(key)
            edges.append(
                GraphEdge(
                    source=e.source_concept,
                    target=e.target_concept,
                    edge_type=e.edge_type,
                    weight=e.weight,
                )
            )

    return UserGraphResponse(
        nodes=nodes,
        edges=edges,
        meta={"total_concepts": total_concepts},
    )


# ---------------------------------------------------------------------------
# Velocity endpoint
# ---------------------------------------------------------------------------

class UserVelocityConcept(BaseModel):
    concept_name: str
    velocity: float        # aggregated weight scaled to match global range
    acceleration: float    # coverage score (% of papers × 50)
    composite_score: float
    trend: str             # accelerating / stable / decelerating
    weeks_of_data: int     # repurposed: number of papers this concept appears in


@router.get("/velocity", response_model=list[UserVelocityConcept])
async def get_user_velocity(
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[UserVelocityConcept]:
    """Return concept prominence scores for the user's uploaded papers."""
    if current_user.get("role") == "demo":
        raise HTTPException(status_code=403, detail="Demo accounts have no personal velocity data")

    user_uuid = uuid.UUID(current_user["sub"])

    concepts = (
        await db.execute(select(UserConcept).where(UserConcept.user_id == user_uuid))
    ).scalars().all()

    if not concepts:
        return []

    # Count distinct papers to compute coverage ratio
    total_papers = len({c.paper_id for c in concepts})
    if total_papers == 0:
        return []

    weight_sum: Counter = Counter()
    paper_set: dict[str, set] = {}
    for c in concepts:
        weight_sum[c.concept] += c.weight
        paper_set.setdefault(c.concept, set()).add(str(c.paper_id))

    result = []
    for concept, agg_weight in weight_sum.most_common(200):
        coverage = len(paper_set[concept]) / total_papers
        # Map to range similar to global velocity scores
        velocity = round(agg_weight * 1000, 1)
        acceleration = round(coverage * 50, 1)
        composite = round(velocity * coverage, 2)

        if coverage >= 0.8:
            trend = "stable"
        elif coverage >= 0.4 or agg_weight > 0.01:
            trend = "accelerating"
        else:
            trend = "decelerating"

        result.append(UserVelocityConcept(
            concept_name=concept,
            velocity=velocity,
            acceleration=acceleration,
            composite_score=composite,
            trend=trend,
            weeks_of_data=len(paper_set[concept]),
        ))

    return sorted(result, key=lambda x: x.composite_score, reverse=True)


# ---------------------------------------------------------------------------
# Prediction endpoint
# ---------------------------------------------------------------------------

_PREDICT_PROMPT = """\
You are a research analyst. A researcher has uploaded {n_papers} papers covering these key concepts:

TOP CONCEPTS (concept: prominence score):
{concepts}

KEY CO-OCCURRING CONCEPT PAIRS:
{edges}

Based on this personal research corpus, generate a structured research analysis.
Respond ONLY with valid JSON matching this exact schema:

{{
  "overall_confidence": "medium",
  "time_horizon_months": 12,
  "emerging_directions": [
    {{"direction": "...", "reasoning": "...", "confidence": "high"}}
  ],
  "underexplored_gaps": [
    {{"gap": "...", "reasoning": "..."}}
  ],
  "predicted_convergences": [
    {{"concept_a": "...", "concept_b": "...", "reasoning": "..."}}
  ]
}}

Rules:
- 3 emerging directions, 3 underexplored gaps, 3 predicted convergences
- confidence values must be exactly "high", "medium", or "low"
- overall_confidence must be exactly "high", "medium", or "low"
- Respond with JSON only, no markdown, no explanation
"""


@router.post("/predict")
async def user_predict(
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate LLM-powered research predictions from the user's uploaded papers."""
    if current_user.get("role") == "demo":
        raise HTTPException(status_code=403, detail="Demo accounts cannot generate predictions")

    user_uuid = uuid.UUID(current_user["sub"])

    concepts = (
        await db.execute(select(UserConcept).where(UserConcept.user_id == user_uuid))
    ).scalars().all()

    if not concepts:
        raise HTTPException(status_code=400, detail="No uploaded papers — upload PDFs first")

    papers = (
        await db.execute(
            select(UserPaper).where(
                UserPaper.user_id == user_uuid,
                UserPaper.status == "processed",
            )
        )
    ).scalars().all()

    edges = (
        await db.execute(
            select(UserGraphEdge).where(UserGraphEdge.user_id == user_uuid)
        )
    ).scalars().all()

    # Build aggregated concept weights
    weight_sum: Counter = Counter()
    for c in concepts:
        weight_sum[c.concept] += c.weight

    top_concepts_str = "\n".join(
        f"- {name}: {round(w, 4)}"
        for name, w in weight_sum.most_common(20)
    )

    # Top edges by weight
    edge_weights: Counter = Counter()
    for e in edges:
        key = tuple(sorted([e.source_concept, e.target_concept]))
        edge_weights[key] += e.weight

    top_edges_str = "\n".join(
        f"- {a} ↔ {b}: {round(w, 5)}"
        for (a, b), w in edge_weights.most_common(15)
    )

    paper_names = [p.filename for p in papers]
    prompt = _PREDICT_PROMPT.format(
        n_papers=len(paper_names),
        concepts=top_concepts_str,
        edges=top_edges_str,
    )

    # Call Ollama — CancelledError propagates cleanly if client disconnects
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as ollama:
            resp = await ollama.post(
                f"{settings.ollama_url}/api/generate",
                json={"model": settings.ollama_predict_model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
    except asyncio.CancelledError:
        raise  # client disconnected — let FastAPI handle it cleanly
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    # Parse JSON from LLM response
    try:
        # Strip any markdown fences the model might add
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        report = json.loads(clean.strip())
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM returned non-JSON response — try again")

    return {
        "topic_context": f"Personal corpus: {', '.join(paper_names[:3])}{'…' if len(paper_names) > 3 else ''}",
        "generated_at": datetime.now(UTC).isoformat(),
        "model_name": settings.ollama_predict_model,
        "is_validated": False,
        "report": report,
    }
