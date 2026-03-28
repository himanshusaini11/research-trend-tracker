"""Auth router — email/password registration, login, and demo token endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.models import User

router = APIRouter(tags=["auth"])


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(data: dict[str, Any], hours: int = 24) -> str:
    """Encode a JWT with the given payload and an expiry of *hours* from now."""
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(hours=hours)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user with email + password and return a JWT access token."""
    existing = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, password_hash=_hash_password(body.password))
    db.add(user)
    await db.flush()  # populate user.id before encoding

    token = _make_token({"sub": str(user.id), "email": user.email, "is_admin": user.is_admin})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password and return a JWT access token (24 h expiry)."""
    user = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user.last_login = datetime.now(UTC)
    token = _make_token({"sub": str(user.id), "email": user.email, "is_admin": user.is_admin})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    user_id = current_user.get("sub")
    if not user_id or user_id == "demo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo accounts have no profile")

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(id=str(user.id), email=user.email, created_at=user.created_at)


@router.get("/demo", response_model=TokenResponse)
async def demo_token(request: Request) -> TokenResponse:
    """Return a short-lived read-only demo JWT (1 h, no registration required).

    The token carries ``role='demo'`` which restricts callers to GET requests only.
    """
    token = _make_token({"sub": "demo", "role": "demo"}, hours=1)
    return TokenResponse(access_token=token)
