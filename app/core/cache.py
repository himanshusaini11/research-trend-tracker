from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

DEFAULT_TTL = 300  # seconds

_redis_client: Redis | None = None  # type: ignore[type-arg]


def _get_client() -> Redis:  # type: ignore[type-arg]
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_dsn,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_redis() -> AsyncGenerator[Redis, None]:  # type: ignore[type-arg]
    yield _get_client()


# ---------------------------------------------------------------------------
# Application lifecycle helper
# ---------------------------------------------------------------------------
async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# ---------------------------------------------------------------------------
# Simple helpers
# ---------------------------------------------------------------------------
async def cache_get(key: str) -> Any | None:
    client = _get_client()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    client = _get_client()
    await client.set(key, json.dumps(value), ex=ttl)


async def cache_delete(key: str) -> None:
    client = _get_client()
    await client.delete(key)
