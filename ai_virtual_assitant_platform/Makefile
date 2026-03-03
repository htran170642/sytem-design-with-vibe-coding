.PHONY: help install install-dev test test-cov test-cov-check test-unit test-integration coverage-open lint format format-check clean run docker-build docker-up docker-down up down

# Default target
help:
	@echo "AIVA - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run              Run the application"
	@echo "  make test             Run all tests"
	@echo "  make test-cov         Run tests with HTML/XML/terminal coverage report"
	@echo "  make test-cov-check   Run tests and fail if coverage < 65 %"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make coverage-open    Open HTML coverage report in browser"
	@echo "  make lint             Run linters"
	@echo "  make format           Format code with black and isort"
	@echo ""
	@echo "Docker:"
	@echo "  make up               Start full stack (shorthand)"
	@echo "  make down             Stop full stack (shorthand)"
	@echo "  make docker-build     Build Docker images"
	@echo "  make docker-up        Start Docker containers"
	@echo "  make docker-down      Stop Docker containers"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove cache and build files"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Running
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	pytest

test-cov:
	pytest --cov=app --cov-report=html:htmlcov --cov-report=term-missing --cov-report=xml

test-cov-check:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=65

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

coverage-open:
	@python -m webbrowser htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html in your browser"

# Code Quality
lint:
	@echo "Running flake8..."
	flake8 app tests
	@echo "Running mypy..."
	mypy app
	@echo "Running pylint..."
	pylint app

format:
	@echo "Running black..."
	black app tests
	@echo "Running isort..."
	isort app tests

format-check:
	black --check app tests
	isort --check-only app tests

# Docker
docker-build:
	docker-compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Shorthands
up:
	docker compose up -d

down:
	docker compose down

docker-logs:
	docker compose logs -f

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist

# Database
db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

db-revision:
	alembic revision --autogenerate -m "$(message)"

# Celery
celery-worker:
	celery -A app.worker worker --loglevel=info

celery-flower:
	celery -A app.worker flower --port=5555