"""Integration tests for /admin/users, /admin/stats, /admin/users/{id}/toggle-admin."""
from __future__ import annotations

import uuid

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.security import create_access_token


def _admin_token(user_id: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "is_admin": True})
    return {"Authorization": f"Bearer {token}"}


def _user_token(user_id: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}


async def _create_user(db: AsyncSession, email: str, is_admin: bool = False) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# /admin/users
# ---------------------------------------------------------------------------

async def test_list_users_requires_admin(test_client: AsyncClient) -> None:
    non_admin_id = str(uuid.uuid4())
    resp = await test_client.get("/api/admin/users", headers=_user_token(non_admin_id))
    assert resp.status_code == 403


async def test_list_users_unauthenticated(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_list_users_returns_all_users(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "admin@example.com", is_admin=True)
    await _create_user(test_db, "user1@example.com")
    await _create_user(test_db, "user2@example.com")

    resp = await test_client.get("/api/admin/users", headers=_admin_token(str(admin.id)))
    assert resp.status_code == 200
    users = resp.json()
    emails = [u["email"] for u in users]
    assert "user1@example.com" in emails
    assert "user2@example.com" in emails


async def test_list_users_response_schema(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "schemaadmin@example.com", is_admin=True)

    resp = await test_client.get("/api/admin/users", headers=_admin_token(str(admin.id)))
    assert resp.status_code == 200
    users = resp.json()
    if users:
        u = users[0]
        assert "id" in u
        assert "email" in u
        assert "is_admin" in u
        assert "created_at" in u


# ---------------------------------------------------------------------------
# /admin/stats
# ---------------------------------------------------------------------------

async def test_admin_stats_requires_admin(test_client: AsyncClient) -> None:
    resp = await test_client.get("/api/admin/stats", headers=_user_token(str(uuid.uuid4())))
    assert resp.status_code == 403


async def test_admin_stats_returns_expected_keys(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "statsadmin@example.com", is_admin=True)

    resp = await test_client.get("/api/admin/stats", headers=_admin_token(str(admin.id)))
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "total_users",
        "admin_users",
        "active_users_7d",
        "total_papers",
        "total_keywords",
        "total_trend_scores",
    ):
        assert key in body, f"Missing key: {key}"


async def test_admin_stats_counts_are_non_negative(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "countsadmin@example.com", is_admin=True)

    resp = await test_client.get("/api/admin/stats", headers=_admin_token(str(admin.id)))
    body = resp.json()
    for key in ("total_users", "admin_users", "total_papers"):
        assert body[key] >= 0


# ---------------------------------------------------------------------------
# /admin/users/{id}/toggle-admin
# ---------------------------------------------------------------------------

async def test_toggle_admin_promotes_user(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "toggler@example.com", is_admin=True)
    target = await _create_user(test_db, "target@example.com", is_admin=False)

    resp = await test_client.patch(
        f"/api/admin/users/{target.id}/toggle-admin",
        headers=_admin_token(str(admin.id)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True


async def test_toggle_admin_demotes_admin(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "demoteradmin@example.com", is_admin=True)
    target = await _create_user(test_db, "demotee@example.com", is_admin=True)

    resp = await test_client.patch(
        f"/api/admin/users/{target.id}/toggle-admin",
        headers=_admin_token(str(admin.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False


async def test_toggle_admin_cannot_change_self(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "selfchanger@example.com", is_admin=True)

    resp = await test_client.patch(
        f"/api/admin/users/{admin.id}/toggle-admin",
        headers=_admin_token(str(admin.id)),
    )
    assert resp.status_code == 400
    assert "own admin" in resp.json()["detail"].lower()


async def test_toggle_admin_user_not_found(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    admin = await _create_user(test_db, "notfoundadmin@example.com", is_admin=True)
    fake_id = str(uuid.uuid4())

    resp = await test_client.patch(
        f"/api/admin/users/{fake_id}/toggle-admin",
        headers=_admin_token(str(admin.id)),
    )
    assert resp.status_code == 404


async def test_toggle_admin_requires_admin(
    test_client: AsyncClient, test_db: AsyncSession
) -> None:
    target = await _create_user(test_db, "toggletarget@example.com")

    resp = await test_client.patch(
        f"/api/admin/users/{target.id}/toggle-admin",
        headers=_user_token(str(uuid.uuid4())),
    )
    assert resp.status_code == 403
