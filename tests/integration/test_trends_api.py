from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount


async def test_trends_requires_auth(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/v1/trends?category=cs.AI")
    assert resp.status_code == 401


async def test_trends_empty_returns_list(
    test_client: AsyncClient, auth_headers: dict
) -> None:
    resp = await test_client.get("/api/v1/trends?category=cs.AI", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_trends_returns_data(
    test_client: AsyncClient, test_db: AsyncSession, auth_headers: dict
) -> None:
    test_db.add(
        KeywordCount(
            keyword="transformer",
            category="cs.AI",
            count=10,
            window_date=datetime.now(UTC),
        )
    )
    await test_db.flush()

    resp = await test_client.get("/api/v1/trends?category=cs.AI", headers=auth_headers)
    assert resp.status_code == 200
    keywords = [item["keyword"] for item in resp.json()]
    assert "transformer" in keywords
