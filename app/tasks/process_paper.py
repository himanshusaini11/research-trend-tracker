"""Celery task: process a user-uploaded PDF through the concept extraction pipeline."""
from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from celery import Task
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.core.config import settings
from app.core.logger import get_logger
from app.core.models import UserConcept, UserGraphEdge, UserJob, UserPaper

log = get_logger(__name__)

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "that", "this",
    "all", "you", "these", "those", "it", "its", "we", "our", "they", "their", "which",
    "who", "what", "how", "when", "where", "as", "if", "not", "no", "also",
    "such", "than", "then", "so", "up", "out", "about", "into", "through",
    "show", "shows", "shown", "use", "used", "using", "based", "paper",
    "propose", "proposed", "presents", "present", "results", "fig", "figure",
    "table", "section", "et", "al",
})
_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def _get_session() -> tuple[Any, Session]:
    engine = create_engine(settings.postgres_dsn_sync, pool_pre_ping=True)
    Sess = sessionmaker(engine)
    return engine, Sess()


def _extract_text(pdf_path: str) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return " ".join(pages)


def _extract_concepts(text: str, top_n: int = 50) -> list[tuple[str, float]]:
    """Return (concept, normalised_weight) pairs using TF counter, same as KeywordIndexer."""
    tokens = _TOKEN_RE.findall(text.lower())
    filtered = [t for t in tokens if t not in _STOPWORDS]
    counts = Counter(filtered)
    total = sum(counts.values()) or 1
    most_common = counts.most_common(top_n)
    return [(word, count / total) for word, count in most_common]


def _build_edges(concepts: list[tuple[str, float]]) -> list[tuple[str, str, float]]:
    """Build CO_OCCURS_WITH edges from top concepts (all pairs, weight = product of weights)."""
    # Use top-20 for edges to keep graph manageable
    top20 = concepts[:20]
    edges = []
    for (src, sw), (tgt, tw) in combinations(top20, 2):
        edges.append((src, tgt, round(sw * tw, 6)))
    return edges


@celery_app.task(
    bind=True,
    name="app.tasks.process_paper.process_user_paper",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def process_user_paper(self: Task, job_id: str) -> dict[str, Any]:
    engine, db = _get_session()
    pdf_path: str | None = None

    try:
        # ── 1. Load job + paper ──────────────────────────────────────────────
        job = db.execute(
            select(UserJob).where(UserJob.id == job_id)
        ).scalar_one()

        job.status = "processing"
        db.commit()

        paper = db.execute(
            select(UserPaper).where(UserPaper.id == job.paper_id)
        ).scalar_one()

        pdf_path = paper.upload_path

        # ── 2. Extract text ──────────────────────────────────────────────────
        text = _extract_text(pdf_path)
        if not text.strip():
            raise ValueError("PDF contains no extractable text")

        # ── 3. Concept extraction ────────────────────────────────────────────
        concepts = _extract_concepts(text, top_n=50)

        # ── 4. Insert user_concepts ──────────────────────────────────────────
        now = datetime.now(UTC)
        concept_rows = [
            UserConcept(
                id=uuid.uuid4(),
                user_id=paper.user_id,
                concept=concept,
                paper_id=paper.id,
                weight=weight,
                created_at=now,
            )
            for concept, weight in concepts
        ]
        db.add_all(concept_rows)

        # ── 5. Insert user_graph_edges ───────────────────────────────────────
        edges = _build_edges(concepts)
        edge_rows = [
            UserGraphEdge(
                id=uuid.uuid4(),
                user_id=paper.user_id,
                source_concept=src,
                target_concept=tgt,
                edge_type="CO_OCCURS_WITH",
                weight=w,
            )
            for src, tgt, w in edges
        ]
        db.add_all(edge_rows)

        # ── 6. Mark job complete ─────────────────────────────────────────────
        job.status = "complete"
        job.completed_at = now
        paper.status = "processed"
        paper.concept_count = len(concepts)
        db.commit()

        # ── 7. Delete raw PDF ────────────────────────────────────────────────
        try:
            Path(pdf_path).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("pdf_delete_failed", path=pdf_path, error=str(exc))

        log.info(
            "paper_processed",
            job_id=job_id,
            paper_id=str(paper.id),
            concepts=len(concepts),
            edges=len(edges),
        )
        return {"status": "complete", "concepts": len(concepts), "edges": len(edges)}

    except Exception as exc:
        db.rollback()
        # Update job to failed; keep PDF for potential retry
        try:
            db.execute(
                update(UserJob)
                .where(UserJob.id == job_id)
                .values(status="failed", error_msg=str(exc)[:500])
            )
            db.execute(
                update(UserPaper)
                .where(UserPaper.id == select(UserJob.paper_id).where(UserJob.id == job_id).scalar_subquery())
                .values(status="failed")
            )
            db.commit()
        except Exception:
            db.rollback()
        log.error("paper_processing_failed", job_id=job_id, error=str(exc))
        raise
    finally:
        db.close()
        engine.dispose()
