"""Integration tests for /upload/papers, /upload/jobs/{id}, /upload/export."""
from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User, UserConcept, UserGraphEdge, UserJob, UserPaper
from app.core.security import create_access_token


async def _create_user(db: AsyncSession, email: str = "uploader@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
    )
    db.add(user)
    await db.flush()
    return user


def _auth(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def _demo_auth() -> dict[str, str]:
    from jose import jwt
    from app.core.config import settings
    token = jwt.encode(
        {"sub": "demo", "role": "demo"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _pdf_upload(filename: str = "test.pdf") -> dict:
    return {"file": (filename, io.BytesIO(b"%PDF-1.4 test content"), "application/pdf")}


# ---------------------------------------------------------------------------
# POST /upload/papers
# ---------------------------------------------------------------------------

async def test_upload_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/api/upload/papers",
        headers=_demo_auth(),
        files=_pdf_upload(),
    )
    assert resp.status_code == 403


async def test_upload_not_pdf_rejected(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "notpdf@example.com")
    resp = await test_client.post(
        "/api/upload/papers",
        headers=_auth(str(user.id)),
        files={"file": ("doc.txt", io.BytesIO(b"text content"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "pdf" in resp.json()["detail"].lower()


async def test_upload_success(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "success@example.com")

    mock_task = MagicMock()
    mock_task.id = str(uuid.uuid4())

    with (
        patch("app.api.routers.upload._save_to_volume", return_value="/tmp/fake.pdf"),
        patch("app.tasks.process_paper.process_user_paper.delay", return_value=mock_task),
    ):
        resp = await test_client.post(
            "/api/upload/papers",
            headers=_auth(str(user.id)),
            files=_pdf_upload("research.pdf"),
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert "paper_id" in body
    assert "processing started" in body["message"].lower()


async def test_upload_user_not_found(test_client: AsyncClient) -> None:
    random_id = str(uuid.uuid4())
    with patch("app.api.routers.upload._save_to_volume", return_value="/tmp/fake.pdf"):
        resp = await test_client.post(
            "/api/upload/papers",
            headers=_auth(random_id),
            files=_pdf_upload(),
        )
    assert resp.status_code == 404


async def test_upload_lifetime_quota_exceeded(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    from app.core.config import settings
    user = User(
        id=uuid.uuid4(),
        email="quota@example.com",
        password_hash=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
        lifetime_uploads=settings.max_user_lifetime_uploads,
    )
    test_db.add(user)
    await test_db.flush()

    with patch("app.api.routers.upload._save_to_volume", return_value="/tmp/fake.pdf"):
        resp = await test_client.post(
            "/api/upload/papers",
            headers=_auth(str(user.id)),
            files=_pdf_upload(),
        )
    assert resp.status_code == 402


# ---------------------------------------------------------------------------
# GET /upload/jobs/{job_id}
# ---------------------------------------------------------------------------

async def test_get_job_status(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "jobstatus@example.com")

    paper = UserPaper(
        id=uuid.uuid4(),
        user_id=user.id,
        filename="paper.pdf",
        status="pending",
        created_at=datetime.now(UTC),
    )
    test_db.add(paper)
    await test_db.flush()

    job = UserJob(
        id=uuid.uuid4(),
        user_id=user.id,
        paper_id=paper.id,
        status="pending",
        created_at=datetime.now(UTC),
    )
    test_db.add(job)
    await test_db.flush()

    resp = await test_client.get(
        f"/api/upload/jobs/{job.id}",
        headers=_auth(str(user.id)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "pending"


async def test_get_job_not_found(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "jobnotfound@example.com")
    fake_job_id = str(uuid.uuid4())
    resp = await test_client.get(
        f"/api/upload/jobs/{fake_job_id}",
        headers=_auth(str(user.id)),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /upload/papers
# ---------------------------------------------------------------------------

async def test_list_papers_empty(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "listpapers@example.com")
    resp = await test_client.get("/api/upload/papers", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_papers_returns_user_papers(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "listpapers2@example.com")
    paper = UserPaper(
        id=uuid.uuid4(),
        user_id=user.id,
        filename="my_paper.pdf",
        status="processed",
        created_at=datetime.now(UTC),
    )
    test_db.add(paper)
    await test_db.flush()

    resp = await test_client.get("/api/upload/papers", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    papers = resp.json()
    assert len(papers) == 1
    assert papers[0]["filename"] == "my_paper.pdf"
    assert papers[0]["status"] == "processed"


async def test_list_papers_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/upload/papers", headers=_demo_auth())
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /upload/export
# ---------------------------------------------------------------------------

async def test_export_empty_data(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "export@example.com")
    resp = await test_client.get("/api/upload/export", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    body = resp.json()
    assert "concepts" in body
    assert "edges" in body
    assert "exported_at" in body
    assert body["concepts"] == []
    assert body["edges"] == []


async def test_export_includes_concepts_and_edges(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "exportfull@example.com")

    paper = UserPaper(
        id=uuid.uuid4(),
        user_id=user.id,
        filename="paper.pdf",
        status="processed",
        created_at=datetime.now(UTC),
    )
    test_db.add(paper)
    await test_db.flush()

    concept = UserConcept(
        id=uuid.uuid4(),
        user_id=user.id,
        concept="neural networks",
        paper_id=paper.id,
        weight=0.05,
        created_at=datetime.now(UTC),
    )
    test_db.add(concept)

    edge = UserGraphEdge(
        id=uuid.uuid4(),
        user_id=user.id,
        source_concept="neural networks",
        target_concept="deep learning",
        edge_type="CO_OCCURS_WITH",
        weight=0.002,
    )
    test_db.add(edge)
    await test_db.flush()

    resp = await test_client.get("/api/upload/export", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["concepts"]) == 1
    assert body["concepts"][0]["concept"] == "neural networks"
    assert len(body["edges"]) == 1
    assert body["edges"][0]["source"] == "neural networks"


async def test_export_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/upload/export", headers=_demo_auth())
    assert resp.status_code == 403
