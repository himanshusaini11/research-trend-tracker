# Research Trend Tracker

> Real-time arXiv paper ingestion, keyword trend analytics, and LLM summarization — built production-ready from day one.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Airflow](https://img.shields.io/badge/Airflow-2.10-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)

---

## What It Does

Research Trend Tracker ingests papers from the arXiv public API on a daily schedule, extracts keywords, computes trending scores over configurable time windows, and exposes the results through a production-grade REST API. An LLM summarization endpoint generates natural language trend summaries using a locally-hosted Ollama model. All functionality is also exposed as an MCP (Model Context Protocol) server for AI agent integration.

**Features:**


- JWT + API key dual authentication
- Redis Token Bucket rate limiting
- Prometheus metrics
- Secrets via pydantic-settings
- Airflow CeleryExecutor DAGs
- FastMCP server interface
- TimescaleDB time-series tables
- Multi-stage Dockerfile, non-root user
- GitHub Actions CI (lint -> test -> build)
- Streamlit analytics dashboard

---

## Architecture

The system is designed as a **modular monolith** with a clean read/write split. Microservices were deliberately avoided — for a single-domain pipeline with no independent scaling requirements, the overhead of inter-service networking, separate deployments, and distributed tracing adds complexity without meaningful benefit. Instead, each concern is isolated into its own Python module with strict boundaries, making the codebase easy to navigate, test, and extend without the operational burden of managing multiple services.

- **Write path**: Airflow DAGs --> `app/ingestion` --> `app/analytics` --> PostgreSQL
- **Read path**: FastAPI --> `app/api` --> `app/analytics` + `app/summarizer` --> PostgreSQL + Redis

```
research-trend-tracker/
├── app/
│   ├── core/          # Config, DB, cache, auth, rate limiting, metrics, logging
│   ├── ingestion/     # arXiv client, keyword extractor, DB writer
│   ├── analytics/     # Trend aggregation, scoring (OLS velocity), topic clustering
│   ├── summarizer/    # LangChain + Ollama LLM chain
│   ├── mcp_server/    # FastMCP tools for AI agent integration
│   └── api/           # FastAPI routers, dependency injection
├── airflow/
│   └── dags/          # arxiv_ingestion (daily) + trend_scoring (daily)
├── scripts/
│   └── dashboard.py   # Streamlit analytics dashboard
├── tests/
│   ├── unit/          # KeywordIndexer, RateLimiter, TrendScorer
│   └── integration/   # Papers API, Trends API, Summarize API
└── infra/
    └── docker/        # Multi-stage Dockerfile
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI + Uvicorn | Async, Pydantic v2 validation |
| Database | PostgreSQL 16 + TimescaleDB | Time-series ready; hypertables configurable post-migration |
| ORM | SQLAlchemy 2.0 + Alembic | Async engine, typed mapped columns |
| Cache | Redis 7 | Trend cache + Token Bucket rate limiting |
| LLM | Ollama (llama3.2) | Runs in Docker, no cloud API needed |
| LLM Chain | LangChain LCEL | `prompt | llm` pipe, `ainvoke()` async |
| Scheduler | Apache Airflow 2.10 | CeleryExecutor, two DAGs |
| MCP | FastMCP | 3 tools: get_trends, get_top_papers, summarize_week |
| Observability | Prometheus + structlog | Per-endpoint metrics, structured JSON logs |
| Dashboard | Streamlit + Plotly | Dark theme, live data from API |
| Testing | pytest + testcontainers | Real Postgres/Redis in tests, 21 tests |
| Packaging | uv | Rust-based, deterministic lockfile |
| CI/CD | GitHub Actions | lint --> test --> docker build |

---

## API Endpoints

| Method | Path | Auth | Rate Limited | Description |
|---|---|---|---|---|
| `GET` | `/health` | None | No | Service health check |
| `GET` | `/api/v1/papers` | JWT / API Key | Yes | List papers by category and date range |
| `GET` | `/api/v1/papers/{arxiv_id}` | JWT / API Key | No | Get single paper by arXiv ID |
| `GET` | `/api/v1/trends` | JWT / API Key | Yes | Get trending keywords for a category |
| `GET` | `/api/v1/trends/summary` | JWT / API Key | Yes | Get pre-computed trend scores from trend_scores table |
| `POST` | `/api/v1/summarize` | JWT / API Key | Yes | LLM-generated trend summary via Ollama |

Authentication accepts either a JWT Bearer token **or** an `X-API-Key` header — whichever is present.

Rate limiting uses a Redis Token Bucket keyed per authenticated identity (not per IP).

---

## Database Schema

```sql
-- Papers ingested from arXiv
papers (
    id              INTEGER PRIMARY KEY,
    arxiv_id        VARCHAR(64) UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    abstract        TEXT NOT NULL,
    authors         TEXT[] NOT NULL,
    categories      TEXT[] NOT NULL,          -- GIN index
    published_at    TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL
)

-- Keyword counts per category per time window
-- (TimescaleDB hypertable on window_date — run SELECT create_hypertable after migration)
keyword_counts (
    id              INTEGER PRIMARY KEY,
    keyword         VARCHAR(256) NOT NULL,
    category        VARCHAR(64) NOT NULL,
    window_date     TIMESTAMPTZ NOT NULL,
    count           INT NOT NULL DEFAULT 0,
    UNIQUE (keyword, category, window_date)   -- upsert target
)

-- Trend scores per keyword per window
-- (TimescaleDB hypertable on window_start — run SELECT create_hypertable after migration)
trend_scores (
    id              INTEGER PRIMARY KEY,
    keyword         VARCHAR(256) NOT NULL,
    category        VARCHAR(64) NOT NULL,
    score           FLOAT NOT NULL,
    trend_direction VARCHAR(16) NOT NULL,     -- 'rising' | 'falling' | 'stable'
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    UNIQUE (keyword, category, window_start)  -- upsert target
)
```

---

## Getting Started

### Prerequisites

- Docker + Docker Compose
- Python 3.12
- [uv](https://github.com/astral-sh/uv) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 1. Clone and install

```bash
git clone https://github.com/himanshusaini11/research-trend-tracker.git
cd research-trend-tracker
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set the two required values:

```env
POSTGRES_PASSWORD=your-password
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### 3. Start services

```bash
# Start Postgres, Redis, Ollama
docker compose up -d

# Wait for Ollama to be ready, then pull the model (~2GB)
docker exec research-trend-tracker-ollama-1 ollama pull llama3.2
```

### 4. Run migrations

```bash
uv run alembic upgrade head
```

### 5. Start the API

```bash
uv run uvicorn app.main:app --reload
# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

### 6. Run the ingestion pipeline

```bash
uv run python -c "
import asyncio
from datetime import UTC, datetime
from app.core.database import AsyncSessionLocal
from app.ingestion.arxiv_client import ArxivClient
from app.ingestion.keyword_indexer import KeywordIndexer
from app.ingestion.trend_writer import TrendWriter
from app.core.config import settings

async def run():
    client = ArxivClient(settings.arxiv_categories, 50, 3.0)
    papers = await client.fetch_recent(days_back=7)
    indexer = KeywordIndexer()
    results = [indexer.extract_keywords(p) for p in papers]
    async with AsyncSessionLocal() as session:
        writer = TrendWriter(session)
        new, skipped = await writer.write_papers(papers)
        written = await writer.write_keywords(results, datetime.now(UTC), papers=papers)
        print(f'Papers: {new} new, {skipped} skipped | Keywords: {written}')

asyncio.run(run())
"
```

### 7. Launch the dashboard

```bash
# Generate a JWT token
uv run python -c "from app.core.security import create_access_token; print(create_access_token({'sub':'demo'}))"

# Start Streamlit
uv run streamlit run scripts/dashboard.py
# Dashboard at http://localhost:8501
```

### 8. Start Airflow (optional)

```bash
docker compose -f docker-compose.airflow.yml up -d
# Airflow UI at http://localhost:8080 (admin/admin)
```

---

## MCP Server

The MCP server exposes three tools for AI agent integration:

```bash
uv run python -m app.mcp_server.server
```

| Tool | Description |
|---|---|
| `get_trends` | Get trending keywords for a category and time window |
| `get_top_papers` | Get recent papers filtered by category |
| `summarize_week` | Generate an LLM summary of this week's research trends |

---

## Running Tests

```bash
# Full suite with coverage
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v
```

Tests use [testcontainers](https://testcontainers-python.readthedocs.io/) to spin up real Postgres and Redis instances — no mocking of infrastructure.

---

## CI/CD Pipeline

GitHub Actions runs on every push to `main` and on pull requests:

1. **lint** — `ruff check` + `mypy` (strict mode, no ignored errors)
2. **test** — full pytest suite with coverage gate (`--cov-fail-under=60`)
3. **build** — multi-stage Docker build, verified by importing the app inside the container

---

## Project Structure

```
app/
├── core/
│   ├── config.py        # pydantic-settings, all env vars
│   ├── database.py      # async engine, session factory, Alembic sync engine
│   ├── models.py        # SQLAlchemy 2.0 ORM models
│   ├── security.py      # JWT creation/verification, API key validation
│   ├── rate_limiter.py  # Redis Token Bucket implementation
│   ├── cache.py         # Async Redis client
│   ├── logger.py        # structlog, env-aware formatting
│   ├── metrics.py       # Prometheus instrumentation
│   └── exceptions.py    # Typed exception hierarchy
├── ingestion/
│   ├── arxiv_client.py  # httpx async client, Atom XML parser
│   ├── keyword_indexer.py # TF-IDF-like extraction, stdlib only
│   └── trend_writer.py  # Idempotent DB writes with ON CONFLICT
├── analytics/
│   ├── aggregator.py    # Keyword aggregation, OLS velocity (stdlib)
│   ├── trend_scorer.py  # Score persistence, trend retrieval
│   └── topic_clusterer.py # Prefix-based clustering (BERTopic in v2)
├── summarizer/
│   ├── chain.py         # LangChain LCEL chain, ainvoke()
│   └── prompts.py       # System + human prompt templates
└── mcp_server/
    ├── server.py        # FastMCP instance
    └── tools.py         # 3 registered tool functions
```

---

## License

MIT

---

Built by [Himanshu Saini](https://github.com/himanshusaini11) · [LinkedIn](https://linkedin.com/in/sainihimanshu)