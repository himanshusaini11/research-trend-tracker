# Research Trend Tracker

> Graph-grounded research prediction engine. Identifies emerging research directions from academic papers using knowledge graphs, citation velocity, and LLM synthesis.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Apache AGE](https://img.shields.io/badge/Apache_AGE-graph-F57F17?style=flat-square)
![Coverage](https://img.shields.io/badge/coverage-85%25+-brightgreen?style=flat-square)

---

## Validated Prediction Results

**Dataset:** 889 arXiv papers, cs.CL + cs.AI, Oct–Dec 2024
**Validated:** March 2026 (3 months after dataset cutoff)

| Prediction | Result | Notes |
|---|---|---|
| Vision-Language Models emerging | ✅ Correct | GPT-4o, Gemini 1.5, LLaVA all surged in early 2025 |
| LLM Interpretability gap | ✅ Correct | Mechanistic interpretability became a major focus in 2025 |
| Multimodal Learning gap | ✅ Correct | Remained an active research area throughout 2025 |
| RL + Knowledge Graphs convergence | ⚠️ Partial | RL scaling was right; KG angle missed |
| Continual Learning emerging | ❌ Missed | Test-time compute was the real story |

**Overall:** 2 strong hits, 2 partial, 1 miss — medium confidence report as expected.

---

## Architecture

```
arXiv API ─────────────────┐
                           ▼
Semantic Scholar API ──► Postgres/TimescaleDB
                           │
                    Entity Extractor (Ollama llama3.2)
                           │
                    Apache AGE Knowledge Graph
                    (Paper, Concept, Author nodes;
                     MENTIONS, BY, CITES, CO_OCCURS_WITH edges)
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   Bridge Node Detector         Velocity Tracker
   (networkx betweenness        (TimescaleDB citation
    centrality, k=100)           acceleration trends)
              └────────────┬────────────┘
                           ▼
                    Graph Analyzer
                    (composite scoring)
                           │
                    Prediction Synthesizer
                    (LLM synthesis over graph signals)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       Report Archive   FastAPI      FastMCP
       (prediction_     (REST API)   (MCP tools)
        reports table)
                           │
                      Streamlit
                      Dashboard
```

**Write path:** Airflow DAGs → `app/ingestion` → `app/analytics` → PostgreSQL
**Graph path:** `scripts/run_graph_pipeline.py` → `app/graph` → Apache AGE + `prediction_reports`
**Read path:** FastAPI / MCP → `app/api` + `app/graph` → PostgreSQL

---

## What's New in v2.0

- **Knowledge graph** — Apache AGE (openCypher on Postgres); no new containers
- **Entity extraction** — Ollama extracts concepts and methods from paper abstracts
- **Citation graph** — Semantic Scholar API adds CITES edges between papers
- **Bridge node detection** — networkx approximate betweenness centrality (k=100) identifies concept bridges
- **Velocity tracking** — TimescaleDB tracks citation acceleration over rolling windows
- **Prediction synthesis** — LLM synthesizes structured reports from graph signals (not raw data)
- **Report validation** — `scripts/validate_prediction.py` records prediction accuracy
- **3 new MCP tools** — `query_knowledge_graph`, `get_prediction_report` added alongside v1 tools
- **Streamlit graph tabs** — Knowledge Graph (pyvis), Prediction Report, Velocity Chart

---

## Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| API | FastAPI + Uvicorn | ≥0.135 / 0.41 | Async, Pydantic v2, CORS, Prometheus |
| Language | Python | 3.12 | Strict type hints throughout |
| ORM | SQLAlchemy | ≥2.0.48 | `mapped_column` style, async engine |
| Driver | asyncpg / psycopg2 | ≥0.31 / 2.9 | asyncpg for app, psycopg2 for Alembic |
| Migrations | Alembic | ≥1.18.4 | autogenerate from models |
| Database | PostgreSQL 16 + TimescaleDB | latest-pg16 | hypertables for keyword_counts/scores |
| Graph DB | Apache AGE | 1.6.0-rc0 | openCypher extension on Postgres |
| Graph lib | networkx | ≥3.0 | betweenness centrality for bridge nodes |
| Graph viz | pyvis | ≥0.3.2 | Interactive HTML graph in Streamlit |
| Cache | Redis | 7-alpine | Token Bucket rate limiting |
| LLM | Ollama (llama3.2) | — | Local, no cloud API required |
| LLM client | LangChain + langchain-ollama | ≥1.2 / 1.0 | Stateless chain, per-request instance |
| Citations | Semantic Scholar API | — | 100 req/5 min free tier |
| Scheduler | Apache Airflow | 2.x | docker-compose.airflow.yml |
| MCP | FastMCP | ≥3.1.0 | 5 tools total |
| Observability | Prometheus + Grafana | — | prometheus-fastapi-instrumentator |
| Logging | structlog | ≥25.5.0 | JSON, request_id/module/duration |
| Auth | python-jose + passlib | ≥3.5 / 1.7 | JWT HS256 + API key dual auth |
| Testing | pytest + pytest-asyncio | ≥9.0 / 1.3 | asyncio_mode=auto, 161 tests |
| Containers | testcontainers | ≥4.14.1 | postgres:16, redis:7-alpine |
| Dashboard | Streamlit + Plotly | ≥1.55 / 6.6 | Dark theme, auto-auth |
| Package mgmt | uv | — | Always use uv, never pip |

---

## Quick Start

**Prerequisites:** Docker, Python 3.12, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/himanshusaini11/research-trend-tracker.git
cd research-trend-tracker
uv sync
cp .env.example .env
# Set POSTGRES_PASSWORD and JWT_SECRET in .env
```

```bash
# 1. Start services (Postgres + TimescaleDB + AGE, Redis, Ollama)
docker compose up -d postgres redis ollama
docker exec research-trend-tracker-ollama-1 ollama pull llama3.2

# Tip: For faster entity extraction, install Ollama natively (ollama.com/download)
# and stop the Docker Ollama: docker compose stop ollama
# Native Ollama uses Mac GPU/Neural Engine — ~5-10x faster than Docker CPU

# 2. Run migrations
uv run alembic upgrade head

# 3. Backfill historical papers (--no-semantic skips Semantic Scholar)
uv run python scripts/backfill_historical.py \
  --start-date 2024-10-01 \
  --end-date 2024-12-31 \
  --categories cs.CL,cs.AI \
  --no-semantic

# 4. Build knowledge graph + generate prediction report
uv run python scripts/run_graph_pipeline.py

# 5. Launch dashboard
uv run streamlit run scripts/dashboard.py
# http://localhost:8501 — no token entry required
```

```bash
# Start the API (optional — dashboard uses it for v1 analytics)
uv run uvicorn app.main:app --reload
# http://localhost:8000/docs
```

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `POSTGRES_PASSWORD` | — | **Yes** | PostgreSQL password |
| `JWT_SECRET` | — | **Yes** | JWT HMAC signing secret |
| `POSTGRES_HOST` | `localhost` | No | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | No | PostgreSQL port |
| `POSTGRES_USER` | `rtt` | No | PostgreSQL user |
| `POSTGRES_DB` | `rtt` | No | PostgreSQL database |
| `REDIS_HOST` | `localhost` | No | Redis host |
| `OLLAMA_URL` | `http://localhost:11434` | No | Ollama API base URL |
| `OLLAMA_MODEL` | `llama3.2` | No | Model for entity extraction + synthesis |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `120` | No | LLM request timeout |
| `ARXIV_CATEGORIES` | `["cs.AI","cs.LG","cs.CL","stat.ML"]` | No | Categories to track |
| `SEMANTIC_SCHOLAR_API_KEY` | — | No | Increases S2 rate limit |
| `GRAPH_TOP_N_CONCEPTS` | `20` | No | Concepts returned by graph analyzer |
| `GRAPH_CENTRALITY_K_SAMPLES` | `100` | No | Pivot nodes for approximate betweenness |
| `RATE_LIMIT_REQUESTS` | `60` | No | Token bucket refill rate |
| `RATE_LIMIT_BURST` | `10` | No | Max burst tokens |

---

## API Endpoints

### v1 — Trend Analytics

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Service health check |
| `GET` | `/api/v1/papers` | JWT / API Key | Papers by category + date range |
| `GET` | `/api/v1/papers/{arxiv_id}` | JWT / API Key | Single paper |
| `GET` | `/api/v1/trends` | JWT / API Key | Trending keywords |
| `GET` | `/api/v1/trends/summary` | JWT / API Key | Pre-scored trend analytics |
| `POST` | `/api/v1/summarize` | JWT / API Key | LLM trend summary |

### v2 — Knowledge Graph + Predictions

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/graph/top-concepts` | JWT / API Key | Bridge nodes + velocity scores |
| `GET` | `/graph/predictions/latest` | JWT / API Key | Most recent prediction report |
| `POST` | `/graph/predictions/generate` | JWT / API Key | Generate new prediction report |

Auth accepts JWT Bearer token **or** `X-API-Key` header. Rate limiting is Redis Token Bucket keyed per identity.

---

## MCP Tools

```bash
uv run python -m app.mcp_server.server
```

| Tool | Signature | Description |
|---|---|---|
| `get_trends` | `(category, window_days, top_n)` | Trending keywords for a category window |
| `get_top_papers` | `(category, days_back, limit)` | Recent papers by category |
| `summarize_week` | `(category, window_days, top_n)` | LLM trend summary |
| `query_knowledge_graph` | `(top_n, trend_filter)` | Bridge nodes with composite scores |
| `get_prediction_report` | `(topic_context)` | Latest prediction report for a topic |

---

## Project Structure

```
research-trend-tracker/
├── app/
│   ├── core/               # Config, DB, cache, auth, rate limiting, metrics, logging
│   ├── api/                # FastAPI routers + dependency injection
│   ├── ingestion/          # ArxivClient, KeywordIndexer, TrendWriter, SemanticScholarClient
│   ├── analytics/          # TrendAggregator, TrendScorer, TopicClusterer, VelocityTracker
│   ├── summarizer/         # LangChain + Ollama chain
│   ├── mcp_server/         # FastMCP server + 5 tools
│   └── graph/              # v2: EntityExtractor, RelationBuilder, BridgeNodeDetector,
│                           #     GraphAnalyzer, PredictionSynthesizer, ReportArchive
├── airflow/dags/           # arxiv_ingestion_dag.py
├── alembic/versions/       # 7 migrations, including AGE extension + v2 tables
├── scripts/
│   ├── backfill_historical.py   # Fetch arXiv date range + Semantic Scholar citations
│   ├── run_graph_pipeline.py    # Entity extraction → graph build → predict → archive
│   ├── validate_prediction.py   # Record prediction accuracy after the fact
│   └── dashboard.py             # Streamlit dashboard (5 tabs)
├── tests/
│   ├── unit/               # 9 test files, no DB/Redis
│   └── integration/        # testcontainers Postgres + Redis
└── infra/docker/           # Multi-stage Dockerfile + Dockerfile.postgres (AGE)
```

---

## Running Tests

```bash
uv run pytest tests/ -v --cov=app --cov-report=term-missing
# 161 tests, ≥80% coverage enforced (--cov-fail-under=80)
```

---

## Known Limitations

- **Entity extraction quality** depends on Ollama model. `llama3.2` (3B) produces noisy concept names — duplicate concepts with minor casing differences (`large language models` vs `Large Language Models`) are common. A larger model or post-processing deduplication would improve graph quality.
- **Semantic Scholar free tier** is capped at 100 req/5 min. For datasets >500 papers, use `--no-semantic` during backfill and add citation edges separately, or provide `SEMANTIC_SCHOLAR_API_KEY`.
- **CO_OCCURS_WITH edges only** — concept similarity is based on co-occurrence in the same paper. Semantic similarity edges (via embeddings) are not yet implemented.
- **No deduplication of concept nodes** — `Large Language Models` and `large language models` are separate nodes in the graph. String normalization planned for v3.
- **BERTopic clustering** not yet implemented. `app/analytics/topic_clusterer.py` uses a prefix heuristic. Planned for v3.

---

## Roadmap

**v3 (planned)**
- Vue 3 + D3.js frontend replacing Streamlit
- BERTopic semantic clustering for concept grouping
- Concept node deduplication / canonicalization
- Semantic Scholar full enrichment (all papers, not just recent)
- Public hosted demo

---

## License

MIT

---

Built by [Himanshu Saini](https://github.com/himanshusaini11) · [LinkedIn](https://www.linkedin.com/in/sainihimanshu/)
