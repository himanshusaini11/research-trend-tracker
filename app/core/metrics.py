from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ---------------------------------------------------------------------------
# Custom metrics
# ---------------------------------------------------------------------------
ingestion_papers_total = Counter(
    "ingestion_papers_total",
    "Total number of papers successfully ingested from arXiv",
    ["category"],
)

trend_query_duration_seconds = Histogram(
    "trend_query_duration_seconds",
    "Duration of trend analytics queries in seconds",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of Redis cache hits",
    ["key_prefix"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of Redis cache misses",
    ["key_prefix"],
)

active_connections = Gauge(
    "active_connections",
    "Number of currently active database connections",
)


# ---------------------------------------------------------------------------
# Instrumentator wiring
# ---------------------------------------------------------------------------
def setup_metrics(app: FastAPI) -> None:
    """Attach prometheus-fastapi-instrumentator to the app and expose /metrics."""
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
