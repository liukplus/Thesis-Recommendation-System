# Thesis Recommendation System

毕业设计项目 — 基于 RAG + Agent 的论文智能检索与推荐系统。

The product answers complex literature-search questions with a deterministic RAG pipeline first and a bounded ReAct-style agent (智能体) as a controlled wrapper around it. Optimize for verifiability (可验证性), replaceability (可替换性), and trustworthiness (可信性).

## Repository layout

- The repository root is a uv workspace: root `pyproject.toml` + tracked `uv.lock`; `backend/` is the only workspace member.
- Backend: FastAPI + Python 3.11. The import root is `app/`; sources live in `backend/src/app` and tests in `backend/tests`.
- Frontend: React 18 + TypeScript + Vite + Zustand + Axios, with SSE streaming. Older notes mentioning Vue are stale.
- Report, defense, and other personal paperwork directories are kept on disk but ignored by Git; they are not application source.

## Verification

Run these from the repository root unless noted:

```bash
make test-unit       # backend unit tests
make lint            # ruff check src/
make typecheck       # mypy src/app
```

Also check formatting without changing files:

```bash
cd backend && uv run ruff format --check src/ tests/
```

Frontend type checking:

```bash
cd frontend && npm run typecheck
```

`frontend/package.json` defines `npm run lint`, but ESLint is not currently declared in `devDependencies`; do not treat frontend lint as a proven gate until that dependency is intentionally added. Do not install dependencies or run mutating formatters without approval. `make format`, dev servers, `make db-init`, Docker commands, cleanup, and report generators remain explicit actions.

## Current LangGraph migration

On branch `langgraph-inte`, the agent and pipeline runtimes are being migrated to LangGraph.

- New runtime code belongs in `backend/src/app/graphs/`: `agent.py`, `pipeline.py`, `streaming.py`, `llm.py`, and `tools.py`.
- Public graph entry points are `build_agent_graph` and `build_pipeline_graph`, with streaming adapters for API responses.
- Tests are in `backend/tests/unit/test_graphs.py`; shared fakes such as `fake_chat_model` and `search_stub` are in `backend/tests/conftest.py`.
- `backend/src/app/agent/loop.py` and `backend/src/app/pipeline/orchestrator.py` are deleted. Do not reintroduce either runtime.
- Keep the API SSE event contracts compatible with `graphs/streaming.py` and the existing React frontend.

## Architecture invariants

These are the formalized design decisions. D1, D2, and D7–D10 are the only existing D-numbers — do not invent D3–D6.

- **D1 — One LLM client.** Every provider call goes through the single OpenAI-compatible client (`base_url` + `api_key` + `model`). No vendor SDKs; provider switching belongs in `llm/factory.py`.
- **D2 — Deterministic pipeline first.** The eight-stage pipeline is the default path. The agent is a bounded wrapper with guardrails: step cap, loop detection, token budget, and error circuit breaking — never an unconstrained loop.
- **D7 — Pre-numbered citations only.** Survey/review output may cite only pre-numbered evidence ids `[1..N]`; never fabricate citation numbers.
- **D8 — Two-level citation verification.** L1 checks that the cited source exists; L2 checks that it actually supports the claim.
- **D9 — Extractive evidence.** An evidence span is stored only when it verbatim-matches the source text.
- **D10 — One context object.** `PipelineContext` is the single mutable object threaded through all pipeline stages.

Some stages and integrations remain skeletons. Make work converge toward these invariants rather than describing planned behavior as finished.

## Backend stack and style

Python 3.11 · FastAPI · Pydantic v2 / pydantic-settings · SQLAlchemy 2.0 async · SQLite by default, PostgreSQL-ready · httpx · LangGraph + langchain-core · CAT APM optional.

- Add full type hints to signatures; validate API boundaries with Pydantic v2 models.
- Use `from app.core.logging import get_logger`; do not use `print` in application code.
- Include module docstrings; prefer functions over classes unless the component holds state.
- Follow Ruff formatting and match the patterns in the file being edited.
- Be conservative with dependencies: prefer boring, stable libraries and justify any new one.
- CAT must safely no-op when its native runtime is unavailable; unit tests must not require Docker, CAT, or external API keys.

## Testing conventions

- `backend/tests/` mirrors `app/`; deterministic core, database, budget, guardrail, and graph logic should be heavily unit-tested.
- LLM-dependent tests assert structure and contracts, not exact generated prose.
- Use the shared LangGraph fakes instead of calling a real model.
- A bug fix starts with a failing regression test. Do not hide or skip failing tests without saying why.
- Conventional commit types are used when work is committed: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

## Reports and thesis honesty (报告真实性)

Thesis materials include `report_build/`, `report/`, `prep/`, `pre-script/`, generated DOCX/PDF/PPTX files, and defense notes.

- Clearly distinguish 设计 (designed/stubbed) from 实现 (implemented). Do not claim Docker, CAT, external LLM, or end-to-end behavior was verified locally when it was only statically designed.
- Recalculate hard-coded metrics (file counts, lines of code, test counts, coverage) immediately before a report submission and state the “as of” date. Existing metrics can become stale during the LangGraph migration.
- Edit draw.io sources under `report_build/diagrams/`, then export PNGs. A missing figure gets a placeholder; never substitute a fabricated or unrelated image.
- `report_build/make_report.py`, `make_ppt.py`, `make_diagrams.py`, and similar generators can overwrite deliverables. Treat them as explicit, approval-required actions.

## Privacy and AI workflow

- Never commit personal reports, PPTs, CVs, defense notes, student-ID-bearing files, or `.env` files. Check `.gitignore` before adding material outside `backend/`, `frontend/`, or tracked `docs/`.
- Read the actual file and function signature before using an interface; do not guess an API.
- Prefer current official docs and changelogs over training-cut memory, especially for LangGraph. Cite URLs when web research changes a decision.
- Keep work scoped to one feature or module at a time. Review `git diff` before asking to commit, and never commit code you could not explain to your advisor.

## Reference documents

- `README.md` — architecture, endpoints, and run instructions.
- `docs/Agent_Design_Risk_Review.md` — agent risk register.
- `docs/Production_Concerns_RAG_Agents.md` — production-readiness concerns.
- `docs/vibe-coding-playbook.md` — personal development protocol notes.
