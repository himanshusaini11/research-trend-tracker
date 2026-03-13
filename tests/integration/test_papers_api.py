from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Paper


def _make_paper(arxiv_id: str, categories: list[str] | None = None) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title="Test Paper About Neural Networks",
        abstract="An abstract about machine learning and deep learning research methods.",
        authors=["Test Author"],
        categories=categories or ["cs.AI"],
        published_at=datetime.now(UTC),
        ingested_at=datetime.now(UTC),
    )


async def test_papers_requires_auth(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/v1/papers?category=cs.AI")
    assert resp.status_code == 401


async def test_papers_returns_list(
    test_client: AsyncClient, test_db: AsyncSession, auth_headers: dict
) -> None:
    test_db.add(_make_paper("2401.10100", ["cs.AI"]))
    await test_db.flush()

    resp = await test_client.get("/api/v1/papers?category=cs.AI", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_papers_filter_by_category(
    test_client: AsyncClient, test_db: AsyncSession, auth_headers: dict
) -> None:
    test_db.add(_make_paper("2401.20100", ["cs.AI"]))
    test_db.add(_make_paper("2401.20101", ["cs.LG"]))
    await test_db.flush()

    resp = await test_client.get("/api/v1/papers?category=cs.AI", headers=auth_headers)
    assert resp.status_code == 200
    papers = resp.json()
    assert all("cs.AI" in p["categories"] for p in papers)
    assert not any(p["arxiv_id"] == "2401.20101" for p in papers)


async def test_paper_by_id_not_found(
    test_client: AsyncClient, auth_headers: dict
) -> None:
    resp = await test_client.get("/api/v1/papers/nonexistent-99999", headers=auth_headers)
    assert resp.status_code == 404


async def test_paper_by_id_found(
    test_client: AsyncClient, test_db: AsyncSession, auth_headers: dict
) -> None:
    test_db.add(_make_paper("2401.30100", ["cs.AI"]))
    await test_db.flush()

    resp = await test_client.get("/api/v1/papers/2401.30100", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["arxiv_id"] == "2401.30100"
