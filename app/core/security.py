from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload["exp"] = expire
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token", detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
# In production, hashed API keys should be stored in the DB. This helper
# performs a constant-time comparison to prevent timing attacks.

def verify_api_key(key: str, expected: str) -> bool:
    return secrets.compare_digest(key.encode(), expected.encode())
