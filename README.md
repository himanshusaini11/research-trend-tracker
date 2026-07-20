# Research Trend Tracker (RTT)

> Graph-grounded research-intelligence platform. Ingests arXiv papers, builds an Apache AGE
> knowledge graph, tracks concept velocity, and uses a local LLM to synthesize structured
> trend reports — plus **ARIS**, an experimental multi-agent LangGraph layer that stress-tests
> research directions. Users can also upload their own PDFs for a personal knowledge graph.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Apache AGE](https://img.shields.io/badge/Apache_AGE-graph-F57F17?style=flat-square)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C?style=flat-square)
![Vue 3](https://img.shields.io/badge/Vue-3.x-42b883?style=flat-square&logo=vue.js&logoColor=white)
![Coverage](https://img.shields.io/badge/coverage-91%25%20local%20·%2060%25%20CI%20gate-brightgreen?style=flat-square)

---

## What it is (and what it isn't)

**What it is:** a production-shaped data + ML system. It fetches arXiv papers, extracts
entities and relations into an Apache AGE knowledge graph, scores concept trends with
deterministic graph metrics (betweenness centrality, velocity, a composite score), retrieves
context via semantic search, and has a local LLM write those signals up as readable trend
reports. On top sits **ARIS**, a 3-persona LangGraph debate layer (Researcher / VC /
Policymaker) that produces a heuristic viability read on a given research direction.

**What it isn't:** a validated predictor or forecaster of research outcomes. ARIS's viability
and adoption labels are **heuristic and have no ground-truth validation** behind them. This is
stated plainly, on purpose — see [Limitations](#known-limitations). The engineering is the
deliverable; the forecasting is framed as an architecture demonstration, not a measured result.

---

## What It Does

Research Trend Tracker ingests arXiv papers, builds a knowledge graph of research concepts,
tracks their velocity over time, and uses a local LLM to synthesize structured trend reports.
Researchers can also upload their own PDFs to get a personal knowledge graph, prominence
scores, and LLM-generated trend reports tailored to their own corpus.

**Global pipeline** — 144,997 papers · 9 categories · 2022–2024 · 2.6M graph edges
**Personal pipeline** — Upload PDFs → extract concepts → personal graph + reports
**ARIS layer (experimental)** — multi-agent LangGraph debate over a research direction

---

## Prediction Case Study (Falsifiability Demonstration)

**Dataset:** 889 arXiv papers, cs.CL + cs.AI, Oct–Dec 2024 (initial run)
**Graded:** March 2026 — 3 months after dataset cutoff, self-graded by the author

| Prediction | Result | Notes |
|---|---|---|
| Vision-Language Models emerging | ✅ Hit | GPT-4o, Gemini 1.5, LLaVA all surged in early 2025 |
| LLM Interpretability gap | ✅ Hit | Mechanistic interpretability became a major 2025 focus |
| Multimodal Learning gap | ✅ Hit | Remained an active research area throughout 2025 |
| RL + Knowledge Graphs convergence | ⚠️ Partial | RL scaling was right; KG angle missed |
| Continual Learning emerging | ❌ Miss | Test-time compute was the real story |

**Result: 3 hits, 1 partial, 1 miss** — kept here *with the miss intact*, because a system
that only shows its wins isn't testable.

> **What this is and isn't.** This is a demonstration that the output is **falsifiable** and
> was checked against reality. It is **not** a statistical accuracy claim: n = 5, self-graded,
> no held-out protocol, no baseline. Describing this as a headline accuracy percentage would
> be misleading, so that framing is avoided. See [Limitations](#known-limitations) for how this
> compares to the published state of the art.

---

## Architecture

```
arXiv API ─────────────────────┐
                               ▼
Semantic Scholar API ──► PostgreSQL / TimescaleDB
                               │
                       Entity Extractor  (qwen3.5:27b)
                               │
                       Apache AGE Knowledge Graph
                       (Concept nodes; MENTIONS,
                        CO_OCCURS_WITH, CITES edges)
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼               ▼
     Bridge Node Detector  Velocity Tracker  Embeddings (pgvector)
     (networkx betweenness (TimescaleDB       │  → Semantic Search
      centrality, k=200)    time-series)       │     + RAG grounding
                └──────────────┼──────────────┘
                               ▼
                       Graph Analyzer  →  Prediction Synthesizer
                       (composite scoring)  (structured JSON report)
                               │
                               ▼
              ARIS — multi-agent LangGraph layer (v3.0.0)
        Researcher / VC / Policymaker personas over a StateGraph:
              scatter ► gather ► converge ► synthesize
              (consensus variance math → heuristic verdict)
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      Report Archive        FastAPI           FastMCP
      (Postgres)            (REST API)        (7 MCP tools)
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
          Vue 3 Frontend            Streamlit Dashboard
          (Knowledge Graph,         (scripts/dashboard.py)
           Predictions, ARIS
           Simulation, Velocity,
           Uploads, Admin)

─── Personal Upload Pipeline ────────────────────────────
User PDF → Celery Worker → PyMuPDF + TF-IDF → UserConcepts
                                                    │
                              ┌─────────────────────┼──────────────┐
                              ▼                     ▼              ▼
                       My Graph               My Papers       My Predictions
```

**Write path:** Airflow DAGs → `app/ingestion` → `app/analytics` → PostgreSQL
**Graph path:** `scripts/run_graph_pipeline.py` → `app/graph` → Apache AGE
**Simulation path:** `app/simulation` (LangGraph StateGraph) → `simulation_results`
**Upload path:** User PDF → `app/api/routers/upload` → Celery → `app/tasks/process_paper`
**Read path:** FastAPI → `app/api` + `app/graph` → PostgreSQL

---

## Features

### Global Knowledge Graph
- **D3 Canvas force graph** — 200 concept nodes, zoom/pan/drag, double-click to zoom to node
- **Trend filtering** — Accelerating / Stable / Decelerating with colour-coded nodes
- **Concept detail panel** — centrality, velocity, acceleration, composite score
- **Top Co-occurring** — real CO_OCCURS_WITH edges from the AGE graph
- **Semantic search** — pgvector cosine retrieval over embedded papers
- **AI concept chat** — LLM answers questions about the selected concept, with optional
  **thinking mode** (shows chain-of-thought reasoning)

### ARIS — Multi-Agent Simulation (Experimental)
> **Clearly labeled experimental and unvalidated.** ARIS runs three persona agents
> (Researcher / VC / Policymaker) over a research direction on a LangGraph StateGraph, then
> derives a consensus verdict from the variance of their answers. It is a demonstration of
> agent-orchestration architecture — **not** a validated predictor of viability. The verdict
> is a heuristic threshold cut, and the labels have no ground truth behind them.

- 3 frozen persona dataclasses; RAG-grounded prompts; consensus variance math
- LangGraph `scatter → gather → converge → synthesize` flow
- Exposed via REST (`/graph/simulation/run`, `/graph/simulation/results`) and 2 MCP tools
- Frontend SimulationView with ConsensusChart + AgentPanel (Pinia store)

### My Graph (Personal)
- Upload up to 30 PDFs (≤20 MB each) via drag-and-drop
- Celery worker extracts top-50 concepts + CO_OCCURS_WITH edges via TF-IDF
- Personal knowledge graph in the same D3 canvas; AI chat tailored to your corpus

### Velocity Chart
- **Global mode** — velocity + composite score charts for 200 concepts, sortable table
- **My Papers mode** — concept prominence and coverage score from uploaded PDFs

### Predictions
- **Global mode** — LLM-synthesized structured report (emerging directions, unexplored gaps,
  predicted convergences) from the 145K-paper graph; archive timeline of past reports
- **My Papers mode** — same schema, grounded in your personal corpus; **Stop** button cancels
  the Ollama call cleanly

### Auth & Admin
- Email/password registration and login; JWT HS256 tokens with auto-refresh
- Demo mode — read-only access to the global graph
- Admin panel — user table, stats dashboard, toggle-admin
- Light / Dark / System theme toggle

---

## Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| API | FastAPI + Uvicorn | ≥0.135 / 0.41 | Async, Pydantic v2, CORS, Prometheus |
| Language | Python | 3.12 | Strict type hints throughout |
| ORM | SQLAlchemy | ≥2.0.48 | `mapped_column` style, async engine |
| Driver | asyncpg / psycopg2 | ≥0.31 / 2.9 | asyncpg for app, psycopg2 for Alembic |
| Migrations | Alembic | ≥1.18.4 | 14 migrations including AGE + upload + simulation tables |
| Database | PostgreSQL 16 + TimescaleDB | latest-pg16 | hypertables for time-series tables |
| Graph DB | Apache AGE | 1.6.0-rc0 | openCypher extension on Postgres |
| Vector / RAG | pgvector | — | cosine semantic search + ARIS grounding |
| Graph lib | networkx | ≥3.0 | betweenness centrality for bridge nodes |
| Agents | LangGraph | — | 3-persona StateGraph, consensus variance math |
| Task queue | Celery + Redis | — | PDF processing, beat scheduler, simulation task |
| PDF extract | PyMuPDF (fitz) | — | Text extraction from uploaded PDFs |
| Frontend | Vue 3 + Vite | 3.x / 5.x | D3.js Canvas force graph, TailwindCSS |
| State mgmt | Pinia | — | Persists UI state across navigation |
| LLM | Ollama | — | qwen3.5:27b — local generation |
| Simulation LLM | Ollama | — | gemma4:e4b — ARIS persona agents |
| LLM client | LangChain + langchain-ollama | ≥1.2 / 1.0 | Trend summarization chain |
| Embeddings | Ollama (mxbai-embed-large) | — | 1024-dim, pgvector RAG |
| Cache | Redis | 7-alpine | Token Bucket rate limiting + Celery broker |
| Citations | Semantic Scholar API | — | 100 req/5 min free tier |
| Scheduler | Apache Airflow | 3.1.8 | docker-compose.airflow.yml |
| MCP | FastMCP | ≥3.1.0 | 7 tools total (incl. 2 ARIS simulation tools) |
| Observability | Prometheus + Grafana | — | prometheus-fastapi-instrumentator |
| Logging | structlog | ≥25.5.0 | JSON, request_id / module / duration |
| Auth | python-jose + bcrypt | ≥3.5 / 4.x | JWT HS256, direct bcrypt |
| Testing | pytest + pytest-asyncio | ≥9.0 / 1.3 | 319 unit tests; 91% local, CI gate 60% |
| Dashboard | Streamlit + Plotly | ≥1.55 / 6.6 | Dark theme, auto-auth |
| Package mgmt | uv | — | Always use `uv`, never `pip` |

> **Two models, deliberately.** qwen3.5:27b handles generation (extraction, prediction
> synthesis, chat) for quality. ARIS's 3-persona simulation loop uses gemma4:e4b instead — a
> smaller, faster model chosen to keep simulation latency down across three agents × multiple
> rounds. This is a latency-vs-quality tradeoff, not a capability upgrade.

---

## Quick Start

**Prerequisites:** Docker, Python 3.12, [uv](https://github.com/astral-sh/uv),
[Ollama](https://ollama.com/download) (native install recommended)

```bash
git clone https://github.com/himanshusaini11/research-trend-tracker.git
cd research-trend-tracker
uv sync
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, JWT_SECRET, and OLLAMA_SIMULATION_MODEL at minimum
```

### 1. Start backing services

```bash
docker compose up -d postgres redis
# Ollama runs natively on the host (not in Compose). Pull the models first:
ollama pull qwen3.5:27b
ollama pull gemma4:e4b       # ARIS simulation model
ollama pull mxbai-embed-large   # embedding model for RAG
```

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

### 5. Backfill papers and build the knowledge graph

```bash
uv run python scripts/backfill_historical.py \
  --start-date 2024-10-01 --end-date 2024-12-31 \
  --categories cs.CL,cs.AI --no-semantic

uv run python scripts/run_graph_pipeline.py
```

### 6. Start Celery workers (uploads + simulation)

```bash
uv run celery -A app.celery_app worker --concurrency=2 --loglevel=info
```

### 7. (Optional) Streamlit dashboard

```bash
uv run streamlit run scripts/dashboard.py
# http://localhost:8501
```

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `POSTGRES_PASSWORD` | — | **Yes** | PostgreSQL password |
| `JWT_SECRET` | — | **Yes** | JWT HMAC signing secret |
| `OLLAMA_SIMULATION_MODEL` | — | **Yes** | ARIS simulation model — required; missing value crashes startup |
| `POSTGRES_HOST` | `localhost` | No | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | No | PostgreSQL port |
| `POSTGRES_USER` | `rtt` | No | PostgreSQL user |
| `POSTGRES_DB` | `rtt` | No | PostgreSQL database |
| `REDIS_HOST` | `localhost` | No | Redis host |
| `OLLAMA_URL` | `http://localhost:11434` | No | Ollama API base URL |
| `OLLAMA_MODEL` | `qwen3.5:27b` | No | Model for extraction, summarization, chat |
| `OLLAMA_PREDICT_MODEL` | `qwen3.5:27b` | No | Model for prediction synthesis |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `1200` | No | LLM timeout |
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
| `GET` | `/api/v1/search` | JWT / API Key | pgvector semantic search |
| `POST` | `/api/v1/summarize` | JWT / API Key | LLM trend summary |

### Knowledge Graph (v2)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/graph/top-concepts` | JWT / API Key | Bridge nodes + velocity scores |
| `GET` | `/graph/predictions/latest` | JWT / API Key | Most recent prediction report |
| `POST` | `/graph/predictions/generate` | JWT / API Key | Generate new prediction |
| `POST` | `/graph/simulation/run` | JWT / API Key | Run an ARIS multi-agent simulation |
| `GET` | `/graph/simulation/results` | JWT / API Key | Retrieve simulation results |

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
| `POST` | `/api/user/graph/predict` | JWT | Generate personal prediction |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/admin/users` | JWT (admin) | All users with metadata |
| `GET` | `/api/admin/stats` | JWT (admin) | System stats |
| `PATCH` | `/api/admin/users/{id}/toggle-admin` | JWT (admin) | Grant / revoke admin role |

Auth accepts JWT Bearer token **or** `X-API-Key` header. Rate limiting is Redis Token Bucket
keyed per identity.

---

## MCP Tools

```bash
uv run python -m app.mcp_server.server
```

| Tool | Description |
|---|---|
| `get_trends` | Trending keywords for a category window |
| `get_top_papers` | Recent papers by category |
| `summarize_week` | LLM trend summary |
| `query_knowledge_graph` | Bridge nodes with composite scores |
| `get_prediction_report` | Latest prediction report for a topic |
| `run_research_simulation` | Dispatch an ARIS multi-agent simulation for a topic's latest prediction |
| `get_simulation_report` | Latest ARIS simulation result — verdicts, consensus, death valleys |

---

## Project Structure

```
research-trend-tracker/
├── app/
│   ├── core/               # Config, DB, cache, auth, rate limiting, metrics, logging
│   ├── api/
│   │   ├── search.py       # pgvector semantic search
│   │   └── routers/        # health, papers, trends, summarize, graph (incl. ARIS),
│   │                       # auth, upload, user_graph, admin
│   ├── ingestion/          # ArxivClient, KeywordIndexer, TrendWriter, SemanticScholarClient
│   ├── analytics/          # TrendAggregator, TrendScorer, TopicClusterer, VelocityTracker
│   ├── graph/              # EntityExtractor, RelationBuilder, BridgeNodeDetector,
│   │   └── extractors/     # GraphAnalyzer, PredictionSynthesizer, ReportArchive
│   │                       # backends: Ollama / AnthropicHaiku / AnthropicSonnet
│   ├── services/           # embedding.py, rag.py, rag_prompt.py
│   ├── summarizer/         # LangChain + Ollama chain
│   ├── simulation/         # ARIS v3.0.0: personas, grounding, consensus, engine, runner
│   ├── mcp_server/         # FastMCP server + 7 tools
│   ├── tasks/              # Celery: embed, process_paper, cleanup, run_simulation
│   └── celery_app.py       # Celery + beat schedule config
├── frontend/src/           # Vue views, components (incl. SimulationView), Pinia stores
├── airflow/dags/           # arxiv_ingestion_dag.py (9 tasks incl. simulate), trend_scoring_dag.py
├── alembic/versions/       # 14 migrations (AGE, pgvector, users, uploads, simulation_results)
├── scripts/                # backfill_historical, run_graph_pipeline, build_cooccurrence (~28h),
│                           # snapshot_db, validate_prediction, dashboard.py
├── tests/
│   ├── unit/               # No DB/Redis — mock all I/O
│   └── integration/        # testcontainers Postgres + Redis
├── docs/                   # Technical_Report.md — canonical narrative
└── infra/docker/           # Multi-stage Dockerfile + Dockerfile.postgres (AGE + pgvector)
```

---

## Running Tests

```bash
uv run pytest tests/unit -v                       # fast, no Docker (319 tests)
uv run pytest tests/integration -v                # requires Docker (testcontainers)
uv run pytest tests/ --cov=app --cov-report=term-missing
# 91% coverage locally; CI gate is --cov-fail-under=60
```

---

## Dataset Facts

| Metric | Value |
|---|---|
| Papers ingested | 144,997 |
| Date range | 2022 – 2024 |
| Categories | cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, stat.ML, cs.IR, eess.SP, eess.IV |
| Concept vertices (raw) | 369,359 |
| Concepts analyzed / scored | ~315 |
| MENTIONS edges | 568,358 |
| USES_METHOD edges | 252,473 |
| CO_OCCURS_WITH edges | 1,827,164 |
| Total graph edges | ~2.65M |
| Papers embedded (RAG) | 4,900 of ~145K (~3.4%) |

---

## Known Limitations

Stated plainly — a technical reviewer will find these anyway, and honesty is worth more than a
superlative.

- **No validated ground truth for ARIS viability labels.** Verdicts are threshold cuts over
  the variance of three LLM answers. Useful as an architecture demo; not a measured predictor.
- **No temporally held-out evaluation.** The relevant published state of the art (e.g.
  Marwitz et al., *Nature Machine Intelligence*) validates comparable predictions with
  temporally held-out link prediction and reported AUROC. **This system has no equivalent and
  does not claim one.** Closing that gap is future work, described honestly rather than implied.
- **RAG grounding is partial.** Only a subset of the corpus is currently embedded
  (4,900 of ~145K, ~3.4%), so retrieval and ARIS grounding draw on a fraction of papers.
- **Consensus math is coarse.** Three agents on a 3-level scale yield a small set of possible
  variance values; the verdict thresholds are intentionally simple.
- **Velocity signal uses token matching** — multi-word concepts are matched against TF-IDF
  unigrams, giving directional signal but losing phrase specificity. Phrase-level storage is
  future work.
- **Concept deduplication gap** — case variants are separate graph nodes; pgvector
  nearest-neighbour dedup is future work.
- **Semantic Scholar enrichment** — CITES edges not yet built for the full 144K dataset.
- **CO_OCCURS_WITH build time** — building edges for 144,997 papers takes ~28 hours (pre-built
  in the data snapshot).
- **Personal upload quota** — 30 lifetime PDFs per user (configurable).

---

## Changelog

### v3.0.0 — ARIS Multi-Agent Layer
- **ARIS** — 3-persona LangGraph StateGraph (Researcher / VC / Policymaker) over a research
  direction, RAG-grounded, with consensus variance math and a heuristic verdict
- REST endpoints (`/graph/simulation/run`, `/graph/simulation/results`), 2 MCP tools, Celery
  task, `simulation_results` migration, and a full frontend SimulationView slice
- Airflow DAG extended to chain the simulation task end-to-end

### v2.3.0 — Personal Research Intelligence
- User PDF uploads (Celery + TF-IDF), personal My Graph / My Papers / My Predictions, admin
  panel, single-model consolidation, thinking mode, state persistence, theming

### v2.2.0 — Data Pipeline Stabilization
- 144,997 papers ingested; 2.6M graph edges; idempotent extraction; pluggable LLM backends

### v2.1.0 — Vue 3 + D3.js Frontend
### v2.0.0 — Knowledge Graph + Prediction Engine

---

## Roadmap

Honest future work, not implied-complete features:

- **Temporally held-out evaluation with a reported metric (AUROC)** — to make ARIS a *measured*
  predictor rather than a heuristic one. This is the headline gap versus published work.
- Full-corpus embedding to broaden RAG grounding
- Semantic Scholar full enrichment — CITES edges for all 144K papers
- pgvector concept deduplication — canonical nodes, merge near-duplicates
- Phrase-level keyword storage for accurate multi-word velocity
- BERTopic semantic clustering; public hosted demo

---

## License

MIT

---

Built by [Himanshu Saini](https://github.com/himanshusaini11) · [LinkedIn](https://www.linkedin.com/in/sainihimanshu/)