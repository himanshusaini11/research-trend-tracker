"""Integration tests for /register, /login, /me, /demo auth endpoints."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# /register
# ---------------------------------------------------------------------------

async def test_register_success(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email(test_client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "pass"}
    await test_client.post("/api/auth/register", json=payload)
    resp = await test_client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


async def test_register_returns_valid_jwt(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/api/auth/register",
        json={"email": "jwtcheck@example.com", "password": "password"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    # Token is non-empty and has three JWT segments
    assert len(token.split(".")) == 3


# ---------------------------------------------------------------------------
# /login
# ---------------------------------------------------------------------------

async def test_login_success(test_client: AsyncClient) -> None:
    email = "loginuser@example.com"
    password = "correctpassword"
    await test_client.post("/api/auth/register", json={"email": email, "password": password})

    resp = await test_client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(test_client: AsyncClient) -> None:
    email = "wrongpass@example.com"
    await test_client.post("/api/auth/register", json={"email": email, "password": "correct"})

    resp = await test_client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_nonexistent_user(test_client: AsyncClient) -> None:
    resp = await test_client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "pass"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

async def test_me_returns_user_profile(test_client: AsyncClient, test_db: AsyncSession) -> None:
    user_id = uuid.uuid4()
    import bcrypt
    user = User(
        id=user_id,
        email="me@example.com",
        password_hash=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
    )
    test_db.add(user)
    await test_db.flush()

    token = create_access_token({"sub": str(user_id), "email": user.email})
    resp = await test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert body["id"] == str(user_id)


async def test_me_demo_token_forbidden(test_client: AsyncClient) -> None:
    from jose import jwt
    from app.core.config import settings
    from datetime import UTC, datetime, timedelta
    token = jwt.encode(
        {"sub": "demo", "role": "demo", "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = await test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_me_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_unknown_user_id(test_client: AsyncClient) -> None:
    """Token with a valid UUID that doesn't exist in DB → 404."""
    random_id = str(uuid.uuid4())
    token = create_access_token({"sub": random_id})
    resp = await test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /demo
# ---------------------------------------------------------------------------

async def test_demo_token_issued(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/auth/demo")
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_demo_token_has_demo_role(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/auth/demo")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    from jose import jwt
    from app.core.config import settings
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload.get("role") == "demo"
    assert payload.get("sub") == "demo"
