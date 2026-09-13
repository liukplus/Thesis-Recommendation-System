# Thesis Recommendation System

Intelligent paper search and recommendation system with an 8-stage RAG pipeline and agentic research assistant.

> 毕业设计项目 — 基于 RAG + Agent 的论文智能推荐系统

## ✨ Features

- 🔍 **Multi-Source Paper Search** — recall papers from local DB, semantic search, and external APIs
- ⚡ **8-Stage RAG Pipeline** — query parsing → recall → fusion → rerank → evidence extraction → survey generation → citation verification → export
- 🤖 **Agent Research Assistant** — ReAct agent with plan-first mode, tool use, and guardrails
- 🔄 **SSE Streaming** — real-time progress updates for both pipeline and agent
- 📚 **Citation Verification** — two-level citation verification (string match + semantic)
- 📦 **Batteries-included Demo** — 30 famous AI/ML papers bundled; everything runs offline with no LLM key, vector DB, Redis, or external APIs
- 🎨 **Modern React UI** — clean, responsive interface with dark mode support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  Home │ Search │ Agent │ Settings  (Zustand + SSE streaming)│
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / SSE
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  API v1 │  │ Pipeline │  │  Agent   │  │  LLM Client  │ │
│  │  Layer  │  │ 8 Stages │  │ ReAct    │  │ OpenAI-compat│ │
│  └─────────┘  └──────────┘  └──────────┘  └──────────────┘ │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │   DB (SQLite)    │  │     Core Utilities               │ │
│  │ SQLAlchemy 2.0   │  │ logging, tracing, exceptions, ids│ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (managed by uv)
- **Node.js 18+** (for frontend)
- **uv** (Python package manager) — `pip install uv`

### 1. Install dependencies

```bash
# Backend (Python)
uv sync

# Frontend (React)
cd frontend && npm install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys (optional — works without LLM in demo mode)
```

### 3. Try the demo (no external services needed)

The app ships with a bundled catalog of 30 well-known AI/ML papers and a fully
offline retrieval stack, so every feature works without an LLM key, embedding
models, a vector DB, Redis, or an external paper API:

- on first startup an empty SQLite DB is auto-seeded with the catalog in dev
  mode (`SEED_DEMO_DATA=true`; set it to `false` to opt out);
- pipeline recall → fusion → rerank run against the catalog with an offline
  IDF-weighted keyword scorer and a popularity fallback, so **any** query
  returns a non-empty, plausibly ranked list;
- the agent's `search_stub` tool searches the same catalog; a built-in
  rule-based planner drives the run when no LLM is configured.

```bash
make db-seed      # seed manually (idempotent — skips if the DB is populated)
make db-reseed    # wipe and reload the demo catalog
```

Try queries such as `graph neural networks`, `reinforcement learning policy
gradient`, `retrieval augmented generation`, or `low-rank adaptation`.

### 4. Start development servers

```bash
# Both backend and frontend (from project root)
make dev

# Or start individually:
make backend-dev    # http://localhost:8000
make frontend-dev   # http://localhost:5173
```

### 5. Verify it works

- **Backend health**: `curl http://localhost:8000/health/live`
- **API docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:5173

## 🐳 Docker Development (with CAT APM)

The backend can run in Docker with Meituan's CAT (Central Application Tracking) APM system for real-time monitoring, distributed tracing, and performance analysis.

### Prerequisites

- **Docker** & **Docker Compose** (v2.22+)
- 4GB+ RAM allocated to Docker

### Quick Start

```bash
# Start all services (backend + CAT + MySQL + frontend)
make docker-up

# Or start just the backend + CAT stack
docker compose --profile cat up -d

# Follow logs
make docker-logs

# Send traffic and get CAT dashboard links
make docker-cat-check
```

> The backend image builds from the **repo root** context (`docker compose build backend`),
> not from `backend/`. `backend/` is a uv workspace member, so `uv.lock` and the root
> `pyproject.toml` must be inside the build context for reproducible `uv sync --frozen`.

### Services

| Service | URL | Purpose |
|---------|-----|---------|
| CAT Dashboard | http://localhost:8080/cat | APM monitoring (admin/admin) |
| Backend API | http://localhost:8000 | FastAPI server |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| Frontend | http://localhost:5173 | React UI |

### CAT Monitoring

CAT provides four monitoring dimensions:

| Concept | Purpose | Our Instrumentation |
|---------|---------|-------------------|
| **Transaction** | Timed code segments | HTTP requests, pipeline stages, DB queries, LLM calls |
| **Event** | One-time occurrences | Log errors/warnings, tool calls, system events |
| **Metric** | Numeric measurements | Request counts, pipeline duration, token usage |
| **Exception** | Error with stack trace | All unhandled exceptions |

CAT aggregates on the server once per minute, so data appears in the dashboard
with a short delay after the first requests.

### Local Development (without Docker)

`cat-sdk` only runs on Linux/Darwin. On Windows the import succeeds but the
native client refuses to initialize, so `cat_integration` stays uninitialized
and every CAT call becomes a no-op — the app runs normally, just without APM
reporting. Tests and local dev need no special handling.

```bash
# Backend runs natively on Windows (CAT falls back to no-op)
make backend-dev

# Frontend is always local
make frontend-dev

# Tests run on the host — the backend image is runtime-only (built --no-dev)
make test
```

### Profiles

| Profile | Services Included |
|---------|------------------|
| `cat` | cat-mysql, cat-server, backend |
| `full` | All services including frontend, redis, qdrant, postgres |
| `backend` | Backend only (no CAT) |
| `redis` / `qdrant` / `postgres` | That single service |

## 📁 Project Structure

```
thesis-recsys/
├── backend/
│   ├── src/app/
│   │   ├── __init__.py        # Version info
│   │   ├── main.py            # FastAPI app factory + lifespan
│   │   ├── config.py          # pydantic-settings config
│   │   ├── core/              # ids, logging, exceptions, tracing
│   │   ├── db/                # SQLAlchemy models, repositories, demo seeder
│   │   ├── mock/              # Bundled 30-paper demo catalog + offline search
│   │   ├── llm/               # OpenAI-compatible client + structured output
│   │   ├── pipeline/          # 8-stage RAG pipeline
│   │   │   ├── context.py     # PipelineContext (shared state)
│   │   │   ├── base.py        # Stage protocol + BaseStage
│   │   │   ├── stages/        # 8 stage implementations
│   │   │   └── orchestrator.py
│   │   ├── agent/             # ReAct agent layer
│   │   │   ├── state.py       # AgentState
│   │   │   ├── tools.py       # Tool registry + built-in tools
│   │   │   ├── loop.py        # ReAct runtime
│   │   │   ├── guardrails.py  # Loop detection, budget, step limits
│   │   │   └── planner.py     # Plan-first mode
│   │   ├── api/               # FastAPI routes
│   │   │   ├── v1/
│   │   │   │   ├── health.py
│   │   │   │   ├── pipeline_routes.py  # sync + SSE
│   │   │   │   ├── agent_routes.py     # sync + SSE + plan
│   │   │   │   └── papers.py          # CRUD
│   │   │   ├── deps.py        # DI dependencies
│   │   │   ├── middleware.py  # trace ID, request logging, CAT middleware
│   │   │   └── errors.py      # global exception handlers
│   │   └── schemas/           # Pydantic models
│   └── tests/
│       └── unit/              # 50+ unit tests
│
├── frontend/
│   ├── src/
│   │   ├── api/               # Axios client + SSE parsing
│   │   ├── store/             # Zustand stores (pipeline, agent)
│   │   ├── components/        # Layout, Chat, Results, Agent, UI
│   │   ├── pages/             # Home, Search, Agent, Settings
│   │   ├── types/             # TypeScript types
│   │   └── styles/            # Global CSS with CSS variables
│   └── package.json
│
├── pyproject.toml             # uv workspace root + dev tools
├── uv.lock                    # Lockfile (workspace-wide)
├── Makefile                   # Dev commands
├── docker-compose.yml         # Docker services (CAT, backend, Redis, etc.)
├── .dockerignore              # Build context is the repo root
├── docker/
│   └── cat/                   # CAT APM configuration
│       ├── client.xml         #   CAT client router config
│       ├── datasources.xml    #   CAT server datasource config
│       └── init.sql           #   CAT database schema
├── backend/
│   ├── Dockerfile             # Backend image (build from repo root)
│   └── src/app/core/
│       ├── cat_integration.py # CAT client wrapper (native + no-op fallback)
│       ├── ids.py
│       ├── logging.py         # JSON logging + CAT LogHandler
│       ├── exceptions.py
│       └── tracing.py         # CAT Transaction backend
├── .env.example               # Environment variables template
```

## 🔧 Development

### Testing

```bash
# Run all backend tests
make test

# Unit tests only
make test-unit

# Frontend type check
cd frontend && npm run typecheck
```

### Code Quality

```bash
make lint       # Ruff lint
make format     # Ruff format
make typecheck  # MyPy
```

### Database

```bash
# Initialize database (create tables)
make db-init

# Load / reload the bundled demo catalog (30 famous AI/ML papers)
make db-seed      # idempotent — no-op when the table already has rows
make db-reseed    # delete existing papers, then insert the catalog
```

The system uses SQLite by default (zero config). Swap to Postgres by setting `DATABASE_URL` in `.env`. In dev, an empty database is auto-seeded on startup; control this with `SEED_DEMO_DATA` in `.env`.

## 🤖 Agent Capabilities

### Tools

| Tool | Description |
|------|-------------|
| `search_stub` | Search the bundled demo catalog (offline keyword + popularity ranking); swap in a real retrieval client for production |
| `summarize_stub` | Summarize text in various styles (stub) |
| `get_help` | Get help about available tools |
| `echo` | Echo back a message (for testing) |

### Guardrails

- **Step limit**: Configurable max steps (default 5)
- **Token budget**: Prompt + completion token tracking
- **Loop detection**: Same tool+args 3x → circuit break
- **Error circuit**: 3 consecutive tool errors → stop

## 📡 API Endpoints

### Pipeline
- `POST /api/v1/pipeline/run` — run full pipeline synchronously
- `POST /api/v1/pipeline/run-stream` — run pipeline with SSE streaming
- `GET /api/v1/pipeline/stages` — list all pipeline stages

### Agent
- `POST /api/v1/agent/run` — run agent synchronously
- `POST /api/v1/agent/run-stream` — run agent with SSE streaming
- `POST /api/v1/agent/plan` — generate plan only (no execution)
- `GET /api/v1/agent/tools` — list available tools

### Papers
- `GET /api/v1/papers` — list/search papers
- `GET /api/v1/papers/{id}` — get paper by ID
- `POST /api/v1/papers` — create paper
- `PATCH /api/v1/papers/{id}` — update paper
- `DELETE /api/v1/papers/{id}` — delete paper

### Health
- `GET /health/live` — liveness probe
- `GET /health/ready` — readiness probe

## 🎯 Pipeline Stages

| # | Stage | Description |
|---|-------|-------------|
| 1 | **Query Parse** | Parse query into structured format (keywords, intent, filters) |
| 2 | **Recall** | Multi-source paper retrieval (local DB, semantic, external) |
| 3 | **Fusion** | RRF fusion + deduplication + citation expansion |
| 4 | **Rerank** | Cross-encoder / LLM-based reranking |
| 5 | **Evidence Extraction** | Extract supporting evidence sentences from top papers |
| 6 | **Survey Generation** | LLM generates grounded answer with citations |
| 7 | **Citation Verification** | Two-level verification (string + semantic) |
| 8 | **Export** | Export to Markdown, BibTeX, JSON |

## 🛠️ Tech Stack

### Backend
- **FastAPI** — async web framework
- **SQLAlchemy 2.0** — ORM (SQLite → Postgres ready)
- **Pydantic v2** — data validation
- **httpx** — async HTTP client for LLM calls
- **uv** — package manager + workspace
- **CAT (Meituan APM)** — distributed monitoring, tracing, and alerting

### Frontend
- **React 18** + **TypeScript**
- **Vite** — dev server + build
- **Zustand** — state management
- **React Router** — routing
- **Axios** — HTTP client
- **SSE** — server-sent events for streaming

### LLM
- OpenAI-compatible API (works with DeepSeek, OpenAI, Zhipu, Tongyi, local models)
- Structured output with Pydantic validation + auto-repair
- Token budget tracking

## 📝 License

MIT
