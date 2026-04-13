"""Integration tests for /user-graph, /user-graph/velocity, /user-graph/predict."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User, UserConcept, UserGraphEdge, UserPaper
from app.core.security import create_access_token


async def _create_user(db: AsyncSession, email: str) -> User:
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


async def _add_concept(
    db: AsyncSession,
    user_id: uuid.UUID,
    paper_id: uuid.UUID,
    concept: str,
    weight: float = 0.05,
) -> UserConcept:
    c = UserConcept(
        id=uuid.uuid4(),
        user_id=user_id,
        concept=concept,
        paper_id=paper_id,
        weight=weight,
        created_at=datetime.now(UTC),
    )
    db.add(c)
    await db.flush()
    return c


async def _add_paper(db: AsyncSession, user_id: uuid.UUID, status: str = "processed") -> UserPaper:
    paper = UserPaper(
        id=uuid.uuid4(),
        user_id=user_id,
        filename="paper.pdf",
        status=status,
        created_at=datetime.now(UTC),
    )
    db.add(paper)
    await db.flush()
    return paper


# ---------------------------------------------------------------------------
# GET /user-graph
# ---------------------------------------------------------------------------

async def test_user_graph_empty(test_client: AsyncClient, test_db: AsyncSession) -> None:
    user = await _create_user(test_db, "emptyugraph@example.com")
    resp = await test_client.get("/api/user/graph", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["meta"]["total_concepts"] == 0


async def test_user_graph_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/user/graph", headers=_demo_auth())
    assert resp.status_code == 403


async def test_user_graph_returns_nodes(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "graphnodes@example.com")
    paper = await _add_paper(test_db, user.id)

    await _add_concept(test_db, user.id, paper.id, "neural", 0.1)
    await _add_concept(test_db, user.id, paper.id, "network", 0.08)

    resp = await test_client.get("/api/user/graph", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    body = resp.json()
    node_ids = [n["id"] for n in body["nodes"]]
    assert "neural" in node_ids
    assert "network" in node_ids


async def test_user_graph_includes_edges(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "graphedges@example.com")
    paper = await _add_paper(test_db, user.id)

    await _add_concept(test_db, user.id, paper.id, "learning", 0.1)
    await _add_concept(test_db, user.id, paper.id, "model", 0.08)

    edge = UserGraphEdge(
        id=uuid.uuid4(),
        user_id=user.id,
        source_concept="learning",
        target_concept="model",
        edge_type="CO_OCCURS_WITH",
        weight=0.008,
    )
    test_db.add(edge)
    await test_db.flush()

    resp = await test_client.get("/api/user/graph", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    edges = resp.json()["edges"]
    assert len(edges) == 1
    assert edges[0]["source"] == "learning"
    assert edges[0]["target"] == "model"


async def test_user_graph_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/user/graph")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /user-graph/velocity
# ---------------------------------------------------------------------------

async def test_user_velocity_empty(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "emptyvel@example.com")
    resp = await test_client.get("/api/user/graph/velocity", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_user_velocity_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/user/graph/velocity", headers=_demo_auth())
    assert resp.status_code == 403


async def test_user_velocity_returns_concepts(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "velconcepts@example.com")
    paper = await _add_paper(test_db, user.id)

    await _add_concept(test_db, user.id, paper.id, "transformer", 0.15)
    await _add_concept(test_db, user.id, paper.id, "attention", 0.10)

    resp = await test_client.get("/api/user/graph/velocity", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    names = [r["concept_name"] for r in results]
    assert "transformer" in names


async def test_user_velocity_schema(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "velschema@example.com")
    paper = await _add_paper(test_db, user.id)
    await _add_concept(test_db, user.id, paper.id, "learning", 0.12)

    resp = await test_client.get("/api/user/graph/velocity", headers=_auth(str(user.id)))
    assert resp.status_code == 200
    item = resp.json()[0]
    for key in ("concept_name", "velocity", "acceleration", "composite_score", "trend", "weeks_of_data"):
        assert key in item, f"Missing key: {key}"
    assert item["trend"] in ("accelerating", "stable", "decelerating")


# ---------------------------------------------------------------------------
# POST /user-graph/predict
# ---------------------------------------------------------------------------

async def test_predict_demo_forbidden(test_client: AsyncClient) -> None:
    resp = await test_client.post("/api/user/graph/predict", headers=_demo_auth())
    assert resp.status_code == 403


async def test_predict_no_concepts_returns_400(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "noconceptspredict@example.com")
    resp = await test_client.post("/api/user/graph/predict", headers=_auth(str(user.id)))
    assert resp.status_code == 400
    assert "upload" in resp.json()["detail"].lower()


async def test_predict_success(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "predictok@example.com")
    paper = await _add_paper(test_db, user.id, status="processed")
    await _add_concept(test_db, user.id, paper.id, "neural", 0.12)
    await _add_concept(test_db, user.id, paper.id, "attention", 0.08)

    report_payload = {
        "overall_confidence": "medium",
        "time_horizon_months": 12,
        "emerging_directions": [
            {"direction": "dir1", "reasoning": "r1", "confidence": "high"}
        ],
        "underexplored_gaps": [
            {"gap": "gap1", "reasoning": "r2"}
        ],
        "predicted_convergences": [
            {"concept_a": "neural", "concept_b": "attention", "reasoning": "r3"}
        ],
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": json.dumps(report_payload)}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.api.routers.user_graph.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await test_client.post("/api/user/graph/predict", headers=_auth(str(user.id)))

    assert resp.status_code == 200
    body = resp.json()
    assert "report" in body
    assert "generated_at" in body
    assert body["is_validated"] is False


async def test_predict_ollama_unavailable(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "ollamafail@example.com")
    paper = await _add_paper(test_db, user.id, status="processed")
    await _add_concept(test_db, user.id, paper.id, "concept", 0.1)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

    with patch("app.api.routers.user_graph.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await test_client.post("/api/user/graph/predict", headers=_auth(str(user.id)))

    assert resp.status_code == 503
    assert "ollama" in resp.json()["detail"].lower()


async def test_predict_llm_returns_bad_json(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    user = await _create_user(test_db, "badjson@example.com")
    paper = await _add_paper(test_db, user.id, status="processed")
    await _add_concept(test_db, user.id, paper.id, "concept", 0.1)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": "not valid json at all"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.api.routers.user_graph.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await test_client.post("/api/user/graph/predict", headers=_auth(str(user.id)))

    assert resp.status_code == 502
