"""Unit tests for app/api/deps.py — mocks all DB and Redis I/O."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# get_db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_db_yields_and_commits() -> None:
    from app.api.deps import get_db

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.deps.AsyncSessionLocal", return_value=mock_ctx):
        gen = get_db()
        session = await gen.__anext__()
        assert session is mock_session

        # Driving the generator to completion triggers the post-yield commit
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_rolls_back_on_exception() -> None:
    from app.api.deps import get_db

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.deps.AsyncSessionLocal", return_value=mock_ctx):
        gen = get_db()
        await gen.__anext__()

        with pytest.raises(ValueError):
            await gen.athrow(ValueError("db error"))

    mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# verify_jwt_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_jwt_token_success() -> None:
    from app.api.deps import verify_jwt_token

    token = create_access_token({"sub": "user-123"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    result = await verify_jwt_token(credentials=credentials)
    assert result["sub"] == "user-123"


@pytest.mark.asyncio
async def test_verify_jwt_token_missing_credentials_raises_401() -> None:
    from app.api.deps import verify_jwt_token

    with pytest.raises(HTTPException) as exc_info:
        await verify_jwt_token(credentials=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_jwt_token_invalid_token_raises_401() -> None:
    from app.api.deps import verify_jwt_token

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.valid.token")
    with pytest.raises(HTTPException) as exc_info:
        await verify_jwt_token(credentials=credentials)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# verify_api_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_api_key_missing_raises_401() -> None:
    from app.api.deps import verify_api_key

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(key=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_invalid_raises_401() -> None:
    from app.api.deps import verify_api_key

    with patch("app.api.deps.settings") as mock_settings:
        mock_settings.api_key = "expected-key"

        with patch("app.core.security.verify_api_key", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(key="wrong-key")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_valid_returns_key() -> None:
    from app.api.deps import verify_api_key

    with patch("app.api.deps.settings") as mock_settings:
        mock_settings.api_key = "secret"

        with patch("app.core.security.verify_api_key", return_value=True):
            result = await verify_api_key(key="secret")

    assert result == "secret"


# ---------------------------------------------------------------------------
# get_current_user — JWT path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_jwt_path() -> None:
    from app.api.deps import get_current_user

    token = create_access_token({"sub": "user-abc"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    mock_request = MagicMock()
    mock_request.method = "GET"

    result = await get_current_user(
        request=mock_request, credentials=credentials, api_key=None
    )
    assert result["sub"] == "user-abc"


@pytest.mark.asyncio
async def test_get_current_user_api_key_path() -> None:
    from app.api.deps import get_current_user

    mock_request = MagicMock()
    mock_request.method = "GET"

    with patch("app.api.deps.settings") as mock_settings:
        mock_settings.api_key = "my-api-key"
        with patch("app.core.security.verify_api_key", return_value=True):
            result = await get_current_user(
                request=mock_request, credentials=None, api_key="my-api-key"
            )

    assert result["sub"] == "api_key"


@pytest.mark.asyncio
async def test_get_current_user_no_auth_raises_401() -> None:
    from app.api.deps import get_current_user

    mock_request = MagicMock()
    mock_request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=mock_request, credentials=None, api_key=None
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_demo_post_raises_403() -> None:
    """Demo tokens cannot make POST requests."""
    from app.api.deps import get_current_user
    from jose import jwt
    from app.core.config import settings

    demo_token = jwt.encode(
        {"sub": "demo", "role": "demo"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=demo_token)
    mock_request = MagicMock()
    mock_request.method = "POST"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=mock_request, credentials=credentials, api_key=None
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_invalid_jwt_falls_through_to_no_auth() -> None:
    """Invalid JWT with no API key → 401."""
    from app.api.deps import get_current_user

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="invalid.token.here"
    )
    mock_request = MagicMock()
    mock_request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=mock_request, credentials=credentials, api_key=None
        )

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_rate_limiter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_rate_limiter_returns_rate_limiter() -> None:
    from app.api.deps import get_rate_limiter
    from app.core.rate_limiter import RateLimiter

    mock_redis = AsyncMock()
    result = await get_rate_limiter(redis=mock_redis)

    assert isinstance(result, RateLimiter)
