from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AuthenticationError
from app.core.rate_limiter import RateLimiter
from app.core.security import verify_token

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Auth schemes
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        return verify_token(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc


async def verify_api_key(
    key: str | None = Security(_api_key_header),
) -> str:
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    # In production the expected key comes from the DB; here we validate a
    # single configured key as a placeholder until the user service is built.
    from app.core.security import verify_api_key as _check

    expected = getattr(settings, "api_key", None)
    if expected is None or not _check(key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return key


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    api_key: str | None = Security(_api_key_header),
) -> dict[str, Any]:
    """Accept either a valid JWT bearer token or a valid API key.

    Tokens with ``role='demo'`` are valid only for GET requests.
    """
    payload: dict[str, Any] | None = None

    if credentials is not None:
        try:
            payload = verify_token(credentials.credentials)
        except AuthenticationError:
            pass

    if payload is None and api_key is not None:
        from app.core.security import verify_api_key as _check

        expected = getattr(settings, "api_key", None)
        if expected and _check(api_key, expected):
            payload = {"sub": "api_key", "key": api_key}

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — provide a bearer token or API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Demo tokens are read-only
    if payload.get("role") == "demo" and request.method != "GET":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo account is read-only",
        )

    return payload


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
async def get_rate_limiter(
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
) -> RateLimiter:
    return RateLimiter(redis)
