# Research Trend Tracker

> Graph-grounded research intelligence platform. Identifies emerging research directions from academic papers using knowledge graphs, citation velocity, LLM synthesis, and personal paper analysis.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Apache AGE](https://img.shields.io/badge/Apache_AGE-graph-F57F17?style=flat-square)
![Vue 3](https://img.shields.io/badge/Vue-3.x-42b883?style=flat-square&logo=vue.js&logoColor=white)
![Coverage](https://img.shields.io/badge/coverage-86%25+-brightgreen?style=flat-square)

---

## What It Does

Research Trend Tracker ingests arXiv papers, builds a knowledge graph of research concepts, tracks their velocity over time, and uses a local LLM to synthesize structured prediction reports. Researchers can also upload their own PDFs to get a personal knowledge graph, prominence scores, and AI predictions tailored to their research corpus.

**Global pipeline** — 144,997 papers · 9 categories · 2022–2024 · 2.6M graph edges
**Personal pipeline** — Upload PDFs → extract concepts → personal graph + predictions

---

## Validated Prediction Results

**Dataset:** 889 arXiv papers, cs.CL + cs.AI, Oct–Dec 2024 (initial validation run)
**Validated:** March 2026 — 3 months after dataset cutoff

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
arXiv API ─────────────────────┐
                               ▼
Semantic Scholar API ──► Postgres / TimescaleDB
                               │
                       Entity Extractor (qwen3.5:27b)
                               │
                       Apache AGE Knowledge Graph
                       (Concept nodes; MENTIONS,
                        CO_OCCURS_WITH, CITES edges)
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
     Bridge Node Detector           Velocity Tracker
     (networkx betweenness          (TimescaleDB time-
      centrality, k=200)             series aggregation)
                └──────────────┬──────────────┘
                               ▼
                       Graph Analyzer
                       (composite scoring)
                               │
                       Prediction Synthesizer
                       (qwen3.5:27b → structured JSON)
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      Report Archive        FastAPI           FastMCP
      (Postgres)            (REST API)        (5 MCP tools)
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
          Vue 3 Frontend            Streamlit Dashboard
          (Knowledge Graph,         (scripts/dashboard.py)
           Predictions,
           Velocity, Uploads,
           Admin Panel)

─── Personal Upload Pipeline ────────────────────────────
User PDF → Celery Worker → PyMuPDF + TF-IDF → UserConcepts
                                                    │
                              ┌─────────────────────┼──────────────┐
                              ▼                     ▼              ▼
                       My Graph               My Papers       My Predictions
                       (KnowledgeGraph.vue)   (VelocityChart) (qwen3.5:27b)
```

**Write path:** Airflow DAGs → `app/ingestion` → `app/analytics` → PostgreSQL
**Graph path:** `scripts/run_graph_pipeline.py` → `app/graph` → Apache AGE
**Upload path:** User PDF → `app/api/routers/upload` → Celery → `app/tasks/process_paper`
**Read path:** FastAPI → `app/api` + `app/graph` → PostgreSQL

---

## Features

### Global Knowledge Graph
- **D3 Canvas force graph** — 200 concept nodes, zoom/pan/drag, double-click to zoom to node
- **Trend filtering** — Accelerating / Stable / Decelerating with colour-coded nodes
- **Model view toggle** — All 145K papers vs. qwen3.5:27b-extracted subset
- **Concept detail panel** — centrality, velocity, acceleration, composite score
- **Top Co-occurring** — real CO_OCCURS_WITH edges from the AGE graph
- **Trend breakdown** — live counts of accelerating/stable/decelerating concepts
- **AI concept chat** — qwen3.5:27b answers questions about the selected concept, with optional **thinking mode** (💭 shows full chain-of-thought reasoning)

### My Graph (Personal)
- Upload up to 30 PDFs (≤20 MB each) via drag-and-drop
- Celery worker extracts top-50 concepts + CO_OCCURS_WITH edges via TF-IDF
- Personal knowledge graph visualised in the same D3 canvas
- Real edge-based co-occurring concepts from your corpus
- AI chat with a prompt tailored to your personal research context

### Velocity Chart
- **Global mode** — velocity + composite score bar charts for 200 concepts, sortable table
- **My Papers mode** — concept prominence (aggregated weight) and coverage score from uploaded PDFs

### Predictions
- **Global mode** — LLM-synthesized structured report (emerging directions, unexplored gaps, predicted convergences) from the 145K-paper graph; archive timeline of past reports
- **My Papers mode** — same report schema but grounded in your personal corpus; generating state persists across navigation; **Stop** button cancels the Ollama call cleanly
- Both modes use **qwen3.5:27b** (~9 min generation time)

### Auth & Admin
- Email/password registration and login; JWT HS256 tokens with auto-refresh
- Demo mode — read-only access to the global graph, no upload or personal features
- Admin panel — user table, stats dashboard, toggle-admin button
- Light / Dark / System theme toggle with no flash-of-wrong-theme

---

## Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| API | FastAPI + Uvicorn | ≥0.135 / 0.41 | Async, Pydantic v2, CORS, Prometheus |
| Language | Python | 3.12 | Strict type hints throughout |
| ORM | SQLAlchemy | ≥2.0.48 | `mapped_column` style, async engine |
| Driver | asyncpg / psycopg2 | ≥0.31 / 2.9 | asyncpg for app, psycopg2 for Alembic |
| Migrations | Alembic | ≥1.18.4 | 9 migrations including AGE + upload tables |
| Database | PostgreSQL 16 + TimescaleDB | latest-pg16 | hypertables for time-series tables |
| Graph DB | Apache AGE | 1.6.0-rc0 | openCypher extension on Postgres |
| Graph lib | networkx | ≥3.0 | betweenness centrality for bridge nodes |
| Task queue | Celery + Redis | — | PDF processing workers, beat scheduler |
| PDF extract | PyMuPDF (fitz) | — | Text extraction from uploaded PDFs |
| Frontend | Vue 3 + Vite | 3.x / 5.x | D3.js Canvas force graph, TailwindCSS |
| State mgmt | Pinia | — | Persists UI state across navigation |
| Visualization | D3.js | 7.x | Canvas force graph, SVG bar charts |
| LLM | Ollama (qwen3.5:27b) | — | All tasks: extraction, prediction, chat |
| LLM client | LangChain + langchain-ollama | ≥1.2 / 1.0 | Trend summarization chain |
| LLM API | Anthropic SDK | latest | Batch API for large-scale entity extraction |
| Cache | Redis | 7-alpine | Token Bucket rate limiting + Celery broker |
| Citations | Semantic Scholar API | — | 100 req/5 min free tier |
| Scheduler | Apache Airflow | 2.x | docker-compose.airflow.yml |
| MCP | FastMCP | ≥3.1.0 | 5 tools total |
| Observability | Prometheus + Grafana | — | prometheus-fastapi-instrumentator |
| Logging | structlog | ≥25.5.0 | JSON, request_id / module / duration |
| Auth | python-jose + bcrypt | ≥3.5 / 4.x | JWT HS256, direct bcrypt (no passlib) |
| Testing | pytest + pytest-asyncio | ≥9.0 / 1.3 | asyncio_mode=auto, ≥80% coverage |
| Dashboard | Streamlit + Plotly | ≥1.55 / 6.6 | Dark theme, auto-auth |
| Package mgmt | uv | — | Always use `uv`, never `pip` |

---

## Quick Start

**Prerequisites:** Docker, Python 3.12, [uv](https://github.com/astral-sh/uv), [Ollama](https://ollama.com/download) (native recommended)

```bash
git clone https://github.com/himanshusaini11/research-trend-tracker.git
cd research-trend-tracker
uv sync
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and JWT_SECRET at minimum
```

### 1. Start backing services

```bash
docker compose up -d postgres redis
# Ollama: native install is ~5–10x faster than Docker on Mac (GPU/Neural Engine)
ollama pull qwen3.5:27b    # ~17 GB — primary model for all tasks
ollama pull llama3.2       # optional fallback / faster testing
```

> **Docker Ollama alternative:** `docker compose up -d ollama` then
> `docker exec research-trend-tracker-ollama-1 ollama pull qwen3.5:27b`

### 2. Run database migrations

```bash
uv run alembic upgrade head
```

### 3. Start the API server

```bash
uv run uvicorn app.main:app --reload
# http://localhost:8000/docs
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

Register an account at the login page, or use the **Try Demo** button for read-only access.

### 5. Backfill papers and build the knowledge graph

```bash
# Fetch arXiv papers for a date range (--no-semantic skips Semantic Scholar)
uv run python scripts/backfill_historical.py \
  --start-date 2024-10-01 \
  --end-date 2024-12-31 \
  --categories cs.CL,cs.AI \
  --no-semantic

# Extract concepts → build graph → generate prediction report
uv run python scripts/run_graph_pipeline.py
```

### 6. Start Celery workers (for PDF uploads)

```bash
# In a separate terminal
uv run celery -A app.celery_app worker --concurrency=2 --loglevel=info
```

### 7. (Optional) Streamlit dashboard

```bash
uv run streamlit run scripts/dashboard.py
# http://localhost:8501 — auto-authenticates via JWT_SECRET
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
| `OLLAMA_MODEL` | `qwen3.5:27b` | No | Model for extraction, summarization, chat |
| `OLLAMA_PREDICT_MODEL` | `qwen3.5:27b` | No | Model for prediction synthesis |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `1200` | No | LLM timeout (qwen3.5:27b needs ~9 min) |
| `ARXIV_CATEGORIES` | `["cs.AI","cs.LG","cs.CL","cs.CV","cs.NE","stat.ML","cs.IR","eess.SP","eess.IV"]` | No | Categories to ingest |
| `SEMANTIC_SCHOLAR_API_KEY` | — | No | Increases S2 rate limit |
| `GRAPH_TOP_N_CONCEPTS` | `200` | No | Concepts per graph analysis run |
| `GRAPH_CENTRALITY_K_SAMPLES` | `200` | No | Pivot nodes for approximate betweenness |
| `UPLOAD_DIR` | `/tmp/rtt-uploads` | No | Local PDF upload staging directory |
| `MAX_UPLOAD_SIZE_MB` | `20` | No | Per-file size limit |
| `MAX_USER_LIFETIME_UPLOADS` | `30` | No | Total upload quota per user |
| `RATE_LIMIT_REQUESTS` | `60` | No | Token bucket refill rate |
| `RATE_LIMIT_BURST` | `10` | No | Max burst tokens |

---

## API Endpoints

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | None | Create account, returns JWT |
| `POST` | `/api/auth/login` | None | Login, returns JWT |
| `GET` | `/api/auth/demo` | None | Demo token (read-only) |

### Trend Analytics (v1)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Service health check |
| `GET` | `/api/v1/papers` | JWT / API Key | Papers by category + date range |
| `GET` | `/api/v1/papers/{arxiv_id}` | JWT / API Key | Single paper |
| `GET` | `/api/v1/trends` | JWT / API Key | Trending keywords |
| `GET` | `/api/v1/trends/summary` | JWT / API Key | Pre-scored trend analytics |
| `POST` | `/api/v1/summarize` | JWT / API Key | LLM trend summary |

### Knowledge Graph (v2)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/graph/top-concepts` | JWT / API Key | Bridge nodes + velocity scores |
| `GET` | `/graph/predictions/latest` | JWT / API Key | Most recent prediction report |
| `POST` | `/graph/predictions/generate` | JWT / API Key | Generate new prediction (5–15 min) |

### User Uploads

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/upload/papers` | JWT | Upload PDF (≤20 MB, max 30 lifetime) |
| `GET` | `/api/upload/papers` | JWT | List uploaded papers + status |
| `GET` | `/api/upload/jobs/{job_id}` | JWT | Poll Celery job status |
| `GET` | `/api/upload/export` | JWT | Download personal graph as JSON |

### Personal Graph

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/user/graph` | JWT | Personal knowledge graph (nodes + edges) |
| `GET` | `/api/user/graph/velocity` | JWT | Concept prominence scores from uploads |
| `POST` | `/api/user/graph/predict` | JWT | Generate personal prediction (5–15 min) |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/admin/users` | JWT (admin) | All users with metadata |
| `GET` | `/api/admin/stats` | JWT (admin) | System stats (papers, keywords, etc.) |
| `PATCH` | `/api/admin/users/{id}/toggle-admin` | JWT (admin) | Grant / revoke admin role |

Auth accepts JWT Bearer token **or** `X-API-Key` header. Rate limiting is Redis Token Bucket keyed per identity (not per IP).

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
│   ├── api/
│   │   └── routers/        # health, papers, trends, summarize, graph,
│   │                       # auth, upload, user_graph, admin
│   ├── ingestion/          # ArxivClient, KeywordIndexer, TrendWriter, SemanticScholarClient
│   ├── analytics/          # TrendAggregator, TrendScorer, TopicClusterer, VelocityTracker
│   ├── summarizer/         # LangChain + Ollama chain
│   ├── mcp_server/         # FastMCP server + 5 tools
│   ├── graph/              # EntityExtractor, RelationBuilder, BridgeNodeDetector,
│   │   └── extractors/     # GraphAnalyzer, PredictionSynthesizer, ReportArchive
│   │                       # backends: OllamaExtractor / AnthropicHaikuExtractor / AnthropicSonnetExtractor
│   ├── tasks/
│   │   ├── process_paper.py  # Celery task: PDF → TF-IDF concepts → user graph
│   │   └── cleanup.py        # Celery beat: expired data + stale upload cleanup
│   └── celery_app.py         # Celery + beat schedule config
├── frontend/
│   └── src/
│       ├── views/          # Login, Dashboard, KnowledgeGraph, PredictionReport,
│       │                   # VelocityChart, UploadPanel, AdminPanel
│       ├── components/     # GraphPanel (D3 Canvas), ConceptChat (qwen3.5 + thinking mode),
│       │                   # NavBar, TrendBar, PredictionCard
│       ├── stores/         # auth, graph, prediction, velocityState, graphState (Pinia)
│       └── services/       # api.js (Axios + JWT interceptor + AbortController)
├── airflow/dags/           # arxiv_ingestion_dag.py
├── alembic/versions/       # 9 migrations (AGE extension + v2 tables + upload tables)
├── scripts/
│   ├── backfill_historical.py   # Fetch arXiv date range + Semantic Scholar citations
│   ├── run_graph_pipeline.py    # Entity extraction → graph build → predict → archive
│   ├── build_cooccurrence.py    # Standalone CO_OCCURS_WITH edge builder (~28h one-off)
│   ├── snapshot_db.py           # pg_dump backup
│   ├── validate_prediction.py   # Record prediction accuracy after the fact
│   └── dashboard.py             # Streamlit dashboard (auto-auth)
├── tests/
│   ├── unit/               # No DB/Redis — mock all I/O
│   └── integration/        # testcontainers Postgres + Redis
└── infra/docker/           # Multi-stage Dockerfile + Dockerfile.postgres (AGE)
```

---

## Running Tests

```bash
uv run pytest tests/ -v --cov=app --cov-report=term-missing
# ≥80% coverage enforced (--cov-fail-under=80)
```

---

## Dataset Facts

| Metric | Value |
|---|---|
| Papers ingested | 144,997 |
| Date range | 2022 – 2024 |
| Categories | cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, stat.ML, cs.IR, eess.SP, eess.IV |
| Concept nodes | 200 |
| MENTIONS edges | 564,664 |
| USES_METHOD edges | 251,538 |
| CO_OCCURS_WITH edges | 1,776,850 |
| Total graph edges | ~2.6M |
| Top concept | Deep Reinforcement Learning (composite score 50.0) |
| Accelerating / Stable / Decelerating | 17 / 106 / 77 |

---

## Known Limitations

- **qwen3.5:27b prediction time** — generating a prediction report takes ~9 minutes on a local machine. The UI persists the generating state across navigation and provides a Stop button to cancel cleanly.
- **Velocity signal uses token matching** — LLM extracts multi-word Title Case concepts ("Large Language Models") but `keyword_counts` stores TF-IDF unigrams. Token-based matching gives directional signal but loses phrase specificity. Phrase-level storage planned for v3.
- **Concept deduplication gap** — "Large Language Models" and "large language models" are separate graph nodes. pgvector nearest-neighbour deduplication planned for v3.
- **Semantic Scholar enrichment** — CITES edges not yet built for the full 144K paper dataset. Use `--no-semantic` flag during backfill or provide `SEMANTIC_SCHOLAR_API_KEY`.
- **CO_OCCURS_WITH build time** — building edges for 144,997 papers takes ~28 hours. Pre-built in the v2.2.0 snapshot.
- **Personal upload quota** — 30 lifetime PDFs per user (configurable via `MAX_USER_LIFETIME_UPLOADS`).
- **AWS deployment** — `infra/aws/` is scaffolded (ECS Fargate + RDS + ElastiCache) but not yet deployed.

---

## Changelog

### v2.3.0 — Personal Research Intelligence
- **User PDF uploads** — drag-and-drop upload panel, Celery background processing, TF-IDF concept extraction, 30-PDF lifetime quota
- **My Graph** — personal D3 knowledge graph from uploaded papers; real edge-based co-occurring concepts; AI chat with personal context
- **My Papers velocity** — concept prominence + coverage scores in the same velocity chart view
- **My Predictions** — qwen3.5:27b generates structured prediction reports from your personal corpus; generating state persists across navigation; Stop button cancels Ollama cleanly
- **Admin panel** — user table, system stats, toggle-admin
- **qwen3.5:27b everywhere** — single model for extraction, prediction synthesis, and concept chat
- **Thinking mode** — 💭 toggle in ConceptChat enables full chain-of-thought reasoning (shown in collapsible block)
- **State persistence** — navigation no longer resets zoom, filters, sort order, or active tab (Pinia stores)
- **Light / dark / system theme** — no flash of wrong theme on load

### v2.2.0 — Data Pipeline Stabilization
- 144,997 papers ingested (2022–2024, 9 categories)
- 2.6M graph edges — 564K MENTIONS + 252K USES_METHOD + 1.77M CO_OCCURS_WITH
- Idempotent extraction, pluggable LLM backends, unicode surrogate fix

### v2.1.0 — Vue 3 + D3.js Frontend
- Interactive knowledge graph, velocity chart, prediction viewer, split-view layout

### v2.0.0 — Knowledge Graph + Prediction Engine
- Apache AGE graph, entity extraction, citation graph, bridge node detection, prediction synthesis

---

## Roadmap

**v2.4.0 (planned)**
- Semantic Scholar full enrichment — CITES edges for all 144K papers
- pgvector concept deduplication — canonical nodes, merge near-duplicates
- Phrase-level keyword storage — accurate velocity for multi-word concepts

**v3.0 (planned)**
- BERTopic semantic clustering for concept grouping
- Public hosted demo
- arXiv paper recommendation based on personal graph overlap

---

## License

MIT

---

Built by [Himanshu Saini](https://github.com/himanshusaini11) · [LinkedIn](https://www.linkedin.com/in/sainihimanshu/)
