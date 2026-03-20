from __future__ import annotations

import time

from redis.asyncio import Redis

from app.core.config import settings


class RateLimiter:
    """Token Bucket rate limiter backed by Redis.

    Each identifier (IP or API key) gets its own bucket stored as a Redis hash:
        rtt:rl:<identifier>  ->  {tokens: float, last_refill: float}

    Refill is calculated lazily on each request using elapsed time since the
    last call, so no background job is required.
    """

    def __init__(
        self,
        redis: Redis,  # type: ignore[type-arg]
        capacity: int | None = None,
        refill_rate: float | None = None,
        burst: int | None = None,
    ) -> None:
        self._redis = redis
        self._capacity: int = capacity or settings.rate_limit_requests
        self._refill_rate: float = refill_rate or (
            settings.rate_limit_requests / settings.rate_limit_window_seconds
        )
        self._burst: int = burst or settings.rate_limit_burst
        self._max_tokens: int = self._capacity + self._burst

    async def is_allowed(self, identifier: str) -> bool:
        """Return True if the request is within the rate limit, False otherwise."""
        key = f"rtt:rl:{identifier}"
        now = time.time()

        async with self._redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    raw = await pipe.hgetall(key)  # type: ignore[misc]  # redis-py pipeline returns Awaitable|value union

                    tokens = float(raw.get("tokens", self._max_tokens))
                    last_refill = float(raw.get("last_refill", now))

                    # Refill tokens based on elapsed time
                    elapsed = now - last_refill
                    tokens = min(self._max_tokens, tokens + elapsed * self._refill_rate)

                    if tokens < 1:
                        await pipe.unwatch()
                        return False

                    tokens -= 1

                    pipe.multi()
                    await pipe.hset(key, mapping={"tokens": tokens, "last_refill": now})  # type: ignore[misc]  # redis-py pipeline returns Awaitable|value union
                    await pipe.expire(key, settings.rate_limit_window_seconds * 2)
                    await pipe.execute()
                    return True
                except Exception:
                    # WATCH detected a concurrent modification — retry
                    continue
