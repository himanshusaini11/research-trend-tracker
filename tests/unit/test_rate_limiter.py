from __future__ import annotations

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from testcontainers.redis import RedisContainer

from app.core.rate_limiter import RateLimiter

# capacity=5, burst=2 → max_tokens=7
_CAPACITY = 5
_BURST = 2
_MAX_TOKENS = _CAPACITY + _BURST


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as rc:
        yield rc


@pytest_asyncio.fixture(scope="function")
async def redis_client(redis_container):
    host = redis_container.get_container_host_ip()
    port = int(redis_container.get_exposed_port(6379))
    client = aioredis.Redis(host=host, port=port, decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def rate_limiter(redis_client) -> RateLimiter:
    return RateLimiter(redis_client, capacity=_CAPACITY, refill_rate=0.001, burst=_BURST)


async def test_first_request_allowed(rate_limiter: RateLimiter) -> None:
    allowed = await rate_limiter.is_allowed("user:first")
    assert allowed is True


async def test_burst_limit_enforced(rate_limiter: RateLimiter) -> None:
    # Drain the full bucket (max_tokens requests) then one more — that last one must be rejected
    results = [await rate_limiter.is_allowed("user:burst") for _ in range(_MAX_TOKENS + 1)]
    assert results.count(False) >= 1


async def test_different_keys_independent(rate_limiter: RateLimiter) -> None:
    # Exhaust key_a well past its limit
    for _ in range(_MAX_TOKENS + 3):
        await rate_limiter.is_allowed("user:key_a")

    # key_b has never been used — its bucket is full
    allowed = await rate_limiter.is_allowed("user:key_b")
    assert allowed is True
