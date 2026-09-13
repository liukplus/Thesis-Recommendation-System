.PHONY: help dev backend-dev frontend-dev test test-unit test-integ lint typecheck format db-init db-seed db-reseed demo clean \
        docker-up docker-down docker-logs docker-build docker-shell docker-test docker-cat-check

help:
	@echo "Thesis Recommendation System"
	@echo ""
	@echo "=== Local Development ==="
	@echo "  make dev            Start both backend (uvicorn) and frontend (vite)"
	@echo "  make backend-dev    Start backend API server"
	@echo "  make frontend-dev   Start frontend dev server"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integ     Run integration tests"
	@echo "  make lint           Run ruff lint"
	@echo "  make format         Run ruff format"
	@echo "  make typecheck      Run mypy"
	@echo "  make db-init        Initialize database (create tables)"
	@echo "  make db-seed        Load demo papers into the (empty) database"
	@echo "  make db-reseed      Wipe and reload the demo papers"
	@echo ""
	@echo "=== Docker (with CAT APM) ==="
	@echo "  make docker-up        Start all services (backend + CAT + MySQL)"
	@echo "  make docker-down      Stop all services"
	@echo "  make docker-logs      Follow logs from all services"
	@echo "  make docker-build     Rebuild backend image"
	@echo "  make docker-shell     Open a shell in the backend container"
	@echo "  make docker-cat-check Send traffic and show CAT dashboard links"
	@echo ""
	@echo "=== Utility ==="
	@echo "  make clean          Clean build artifacts and caches"

dev:
	@echo "Starting backend and frontend..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@$(MAKE) -j2 backend-dev frontend-dev

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -v

test-unit:
	cd backend && uv run pytest tests/unit -v

test-integ:
	cd backend && uv run pytest tests/integration -v

lint:
	cd backend && uv run ruff check src/

format:
	cd backend && uv run ruff format src/ tests/

typecheck:
	cd backend && uv run mypy src/app

db-init:
	cd backend && uv run python -c "from app.db.session import init_db; init_db()"

db-seed:
	cd backend && uv run python -m app.db.seed

db-reseed:
	cd backend && uv run python -m app.db.seed --reset

demo:
	@echo "=== Thesis RecSys Demo ==="
	@echo ""
	@echo "Starting backend and frontend..."
	@echo "  Backend API:  http://localhost:8000"
	@echo "  API Docs:    http://localhost:8000/docs"
	@echo "  Frontend:    http://localhost:5173"
	@echo ""
	@echo "Try these queries:"
	@echo "  - 'survey on deep learning for NLP'"
	@echo "  - 'transformer architecture latest advances'"
	@echo "  - 'reinforcement learning in robotics'"
	@echo ""
	@$(MAKE) -j2 backend-dev frontend-dev

# ── Docker ────────────────────────────────────

docker-up:
	@echo "Starting all services with CAT APM..."
	@echo "  CAT Dashboard: http://localhost:8080/cat"
	@echo "  Backend API:   http://localhost:8000"
	@echo "  API Docs:      http://localhost:8000/docs"
	@echo "  Frontend:      http://localhost:5173"
	docker compose --profile full up -d
	@echo ""
	@echo "Services started. Use 'make docker-logs' to follow logs."

docker-down:
	docker compose --profile full down

docker-logs:
	docker compose --profile full logs -f

docker-build:
	docker compose build backend

docker-shell:
	docker compose exec backend bash

# The backend image is a runtime image (built with --no-dev, tests excluded),
# so tests run on the host against the dev venv.
docker-test: test

# Generate some traffic, then point at the CAT dashboard to confirm reporting.
docker-cat-check:
	@echo "Sending requests to the backend..."
	@for i in 1 2 3 4 5; do curl -sf http://localhost:8000/health/live >/dev/null && echo "  ok $$i" || echo "  FAILED $$i"; done
	@echo ""
	@echo "CAT aggregates once per minute. Check:"
	@echo "  Transactions: http://localhost:8080/cat/r/t?domain=thesis-recsys"
	@echo "  Events:       http://localhost:8080/cat/r/e?domain=thesis-recsys"
	@echo "  Problems:     http://localhost:8080/cat/r/p?domain=thesis-recsys"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist backend/*.egg-info frontend/dist frontend/node_modules/.vite
