from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.summarizer.schemas import TrendSummaryOutput


async def test_summarize_requires_auth(test_client: AsyncClient) -> None:
    resp = await test_client.post("/api/v1/summarize", json={"category": "cs.AI"})
    assert resp.status_code == 401


async def test_summarize_with_mock_chain(
    test_client: AsyncClient, auth_headers: dict
) -> None:
    fixed_output = TrendSummaryOutput(
        category="cs.AI",
        window_days=7,
        summary="Research in AI is accelerating with transformer models.",
        keywords_covered=["transformer", "attention"],
        generated_at=datetime.now(UTC),
        model_used="qwen3.5:27b",
    )

    with patch(
        "app.api.routers.summarize.TrendSummarizerChain.summarize",
        new_callable=AsyncMock,
        return_value=fixed_output,
    ):
        resp = await test_client.post(
            "/api/v1/summarize",
            json={"category": "cs.AI"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "cs.AI"
    assert data["window_days"] == 7
    assert "summary" in data
    assert "keywords_covered" in data
    assert "generated_at" in data
