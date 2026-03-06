.DEFAULT_GOAL := help
VENV := $(shell poetry env info --path 2>/dev/null)
PYTHON := $(VENV)/bin/python
LOCUST := $(VENV)/bin/locust

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo "Flash Sale System — available targets:"
	@echo ""
	@echo "  Dev environment"
	@echo "    install        Install all dependencies (Python 3.12)"
	@echo "    dev            Start infra + API in dev mode (hot-reload)"
	@echo "    worker         Start worker locally"
	@echo ""
	@echo "  Docker"
	@echo "    build          Build API + Worker Docker images"
	@echo "    up             Start full stack via docker-compose"
	@echo "    down           Stop all containers"
	@echo "    logs           Tail logs from all services"
	@echo "    ps             Show container status"
	@echo ""
	@echo "  Database"
	@echo "    migrate        Run Alembic migrations (upgrade head)"
	@echo "    migrate-down   Rollback last migration"
	@echo "    seed           Preload stock into Redis"
	@echo ""
	@echo "  Testing"
	@echo "    test           Run unit + integration tests"
	@echo "    test-cov       Run tests with coverage report"
	@echo "    load           Run Locust load test (headless, 1k users)"
	@echo "    test-no-oversell    Verify atomic stock decrement"
	@echo "    test-crash     Failure injection: worker crash"
	@echo "    test-restart   Failure injection: Redis restart"
	@echo "    test-slowdb    Failure injection: DB slowdown"
	@echo ""
	@echo "  Code quality"
	@echo "    lint           Run Ruff linter"
	@echo "    fmt            Auto-format with Ruff"
	@echo "    typecheck      Run MyPy type checker"
	@echo ""
	@echo "  Cleanup"
	@echo "    clean          Remove __pycache__ and .pyc files"
	@echo "    clean-docker   Remove project Docker images"


# ── Dev environment ───────────────────────────────────────────────────────────

.PHONY: install
install:
	poetry env use python3.12
	poetry install

.PHONY: dev
dev:
	$(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: worker
worker:
	$(PYTHON) -m worker.main


# ── Docker ────────────────────────────────────────────────────────────────────

.PHONY: build
build:
	docker build -f Dockerfile.api    -t flash-sale-api:local    .
	docker build -f Dockerfile.worker -t flash-sale-worker:local .

.PHONY: up
up:
	docker compose up --build -d
	@echo "API → http://localhost:8000"
	@echo "Metrics → http://localhost:8000/metrics"

.PHONY: down
down:
	docker compose down

.PHONY: logs
logs:
	docker compose logs -f

.PHONY: ps
ps:
	docker compose ps


# ── Database ──────────────────────────────────────────────────────────────────

.PHONY: migrate
migrate:
	$(PYTHON) -m alembic upgrade head

.PHONY: migrate-down
migrate-down:
	$(PYTHON) -m alembic downgrade -1

.PHONY: seed
seed:
	@read -p "Product ID: " pid; \
	read -p "Stock count: " n; \
	$(PYTHON) infrastructure/scripts/preload_stock.py --product $$pid --stock $$n --force


# ── Testing ───────────────────────────────────────────────────────────────────

.PHONY: test
test:
	$(PYTHON) -m pytest tests/ -v --no-header

.PHONY: test-cov
test-cov:
	$(PYTHON) -m pytest tests/ -v --no-header \
		--cov=api --cov=worker --cov=shared \
		--cov-report=term-missing \
		--cov-report=html:htmlcov

.PHONY: load
load:
	$(LOCUST) -f tests/load/locustfile.py \
		--headless -u 1000 -r 100 --run-time 30s \
		--host http://localhost:8000

.PHONY: test-no-oversell
test-no-oversell:
	$(PYTHON) infrastructure/scripts/test_no_oversell.py

.PHONY: test-crash
test-crash:
	$(PYTHON) infrastructure/scripts/test_worker_crash.py

.PHONY: test-restart
test-restart:
	$(PYTHON) infrastructure/scripts/test_redis_restart.py

.PHONY: test-slowdb
test-slowdb:
	$(PYTHON) infrastructure/scripts/test_db_slowdown.py


# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: lint
lint:
	$(VENV)/bin/ruff check api/ worker/ shared/

.PHONY: fmt
fmt:
	$(VENV)/bin/ruff format api/ worker/ shared/

.PHONY: typecheck
typecheck:
	$(VENV)/bin/mypy api/ worker/ shared/


# ── Cleanup ───────────────────────────────────────────────────────────────────

.PHONY: clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

.PHONY: clean-docker
clean-docker:
	docker rmi flash-sale-api:local flash-sale-worker:local 2>/dev/null || true
