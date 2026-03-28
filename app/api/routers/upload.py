"""Upload router — PDF ingestion, job tracking, and user data export."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.models import User, UserConcept, UserGraphEdge, UserJob, UserPaper

router = APIRouter(tags=["upload"])

_MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PaperOut(BaseModel):
    id: str
    filename: str
    status: str
    concept_count: int
    created_at: datetime


class JobOut(BaseModel):
    job_id: str
    paper_id: str
    status: str
    error_msg: str | None
    created_at: datetime
    completed_at: datetime | None


class UploadResponse(BaseModel):
    job_id: str
    paper_id: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_real_user(current_user: dict[str, Any]) -> None:
    if current_user.get("role") == "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts cannot upload papers — please register",
        )


def _save_to_volume(user_id: str, file_id: str, data: bytes) -> str:
    """Save raw bytes to local volume. Returns absolute file path."""
    dir_path = Path(settings.upload_dir) / user_id
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{file_id}.pdf"
    file_path.write_bytes(data)
    return str(file_path)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/papers", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_paper(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UploadResponse:
    """Upload a PDF for concept extraction. Returns a job_id for status polling."""
    _require_real_user(current_user)

    # ── Validate file type ───────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    user_id_str: str = current_user["sub"]
    user_uuid = uuid.UUID(user_id_str)

    # ── Load user + quota checks ─────────────────────────────────────────────
    user = (await db.execute(select(User).where(User.id == user_uuid))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.lifetime_uploads >= settings.max_user_lifetime_uploads:
        raise HTTPException(
            status_code=402,
            detail=f"Lifetime upload limit of {settings.max_user_lifetime_uploads} reached",
        )

    active_count = (
        await db.execute(
            select(func.count()).select_from(UserPaper).where(
                UserPaper.user_id == user_uuid,
                UserPaper.status.in_(["pending", "processing", "processed"]),
            )
        )
    ).scalar_one()

    if active_count >= settings.max_user_files:
        raise HTTPException(
            status_code=409,
            detail=f"Max {settings.max_user_files} concurrent papers — delete some before uploading more",
        )

    # ── Save file + create DB rows ───────────────────────────────────────────
    file_id = str(uuid.uuid4())
    upload_path = _save_to_volume(user_id_str, file_id, data)

    paper = UserPaper(
        id=uuid.UUID(file_id),
        user_id=user_uuid,
        filename=file.filename,
        upload_path=upload_path,
        status="pending",
        created_at=datetime.now(UTC),
    )
    db.add(paper)
    await db.flush()

    job = UserJob(
        id=uuid.uuid4(),
        user_id=user_uuid,
        paper_id=paper.id,
        status="pending",
        created_at=datetime.now(UTC),
    )
    db.add(job)

    user.lifetime_uploads += 1
    await db.flush()

    # ── Enqueue Celery task ──────────────────────────────────────────────────
    from app.tasks.process_paper import process_user_paper  # noqa: PLC0415
    task = process_user_paper.delay(str(job.id))
    job.celery_task_id = task.id

    return UploadResponse(
        job_id=str(job.id),
        paper_id=str(paper.id),
        message="Upload received — processing started",
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> JobOut:
    """Poll the status of a paper processing job."""
    user_uuid = uuid.UUID(current_user["sub"]) if current_user.get("role") != "demo" else None

    job = (
        await db.execute(select(UserJob).where(UserJob.id == job_id))
    ).scalar_one_or_none()

    if not job or (user_uuid and job.user_id != user_uuid):
        raise HTTPException(status_code=404, detail="Job not found")

    return JobOut(
        job_id=str(job.id),
        paper_id=str(job.paper_id),
        status=job.status,
        error_msg=job.error_msg,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/papers", response_model=list[PaperOut])
async def list_papers(
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[PaperOut]:
    """List all papers uploaded by the current user."""
    _require_real_user(current_user)
    user_uuid = uuid.UUID(current_user["sub"])

    papers = (
        await db.execute(
            select(UserPaper)
            .where(UserPaper.user_id == user_uuid)
            .order_by(UserPaper.created_at.desc())
        )
    ).scalars().all()

    return [
        PaperOut(
            id=str(p.id),
            filename=p.filename,
            status=p.status,
            concept_count=p.concept_count,
            created_at=p.created_at,
        )
        for p in papers
    ]


@router.get("/export")
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    """Export the user's concepts and graph edges as downloadable JSON."""
    _require_real_user(current_user)
    user_uuid = uuid.UUID(current_user["sub"])

    concepts = (
        await db.execute(
            select(UserConcept).where(UserConcept.user_id == user_uuid)
        )
    ).scalars().all()

    edges = (
        await db.execute(
            select(UserGraphEdge).where(UserGraphEdge.user_id == user_uuid)
        )
    ).scalars().all()

    user = (await db.execute(select(User).where(User.id == user_uuid))).scalar_one()

    payload = {
        "exported_at": datetime.now(UTC).isoformat(),
        "user_email": user.email,
        "concepts": [
            {"concept": c.concept, "paper_id": str(c.paper_id), "weight": c.weight}
            for c in concepts
        ],
        "edges": [
            {
                "source": e.source_concept,
                "target": e.target_concept,
                "edge_type": e.edge_type,
                "weight": e.weight,
            }
            for e in edges
        ],
    }

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=rtt-my-graph.json"},
    )
