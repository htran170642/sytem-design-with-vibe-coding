.PHONY: help venv install install-dev setup clean test lint format run-ingestion run-query docker-up docker-down kafka-up kafka-down kafka-init kafka-logs kafka-topics

help:
	@echo "Available commands:"
	@echo "  make venv           - Create virtual environment"
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make setup          - Full setup (venv + deps + hooks)"
	@echo "  make verify         - Verify project setup"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make clean-all      - Clean everything including venv"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo "  make run-ingestion  - Run ingestion service"
	@echo "  make run-query      - Run query service"
	@echo ""
	@echo "Kafka/Docker commands:"
	@echo "  make kafka-up       - Start Redpanda (Kafka)"
	@echo "  make kafka-down     - Stop Redpanda"
	@echo "  make kafka-init     - Initialize Kafka topics"
	@echo "  make kafka-logs     - View Redpanda logs"
	@echo "  make kafka-topics   - List Kafka topics"
	@echo "  make docker-up      - Start all services with docker-compose"
	@echo "  make docker-down    - Stop all services"

venv:
	@echo "Creating virtual environment..."
	python3 -m venv venv
	@echo ""
	@echo "Virtual environment created! Activate it with:"
	@echo "  source venv/bin/activate    (Linux/Mac)"
	@echo "  venv\\Scripts\\activate      (Windows)"
	@echo ""

install:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️  Warning: No virtual environment detected!"; \
		echo "It's recommended to use a virtual environment."; \
		echo "Run: make venv && source venv/bin/activate"; \
		echo ""; \
	fi
	pip install -e .

install-dev:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️  Warning: No virtual environment detected!"; \
		echo "It's recommended to use a virtual environment."; \
		echo "Run: make venv && source venv/bin/activate"; \
		echo ""; \
	fi
	pip install -e ".[dev]"

setup: install-dev
	pre-commit install
	cp .env.example .env
	@echo "Setup complete! Edit .env with your configuration."

setup-full: venv
	@echo "Activating venv and installing dependencies..."
	@echo "Please run these commands manually:"
	@echo "  source venv/bin/activate"
	@echo "  make install-dev"
	@echo "  make setup"

verify:
	python scripts/verify_setup.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/

clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf venv/
	@echo "All clean!"

test:
	pytest

test-cov:
	pytest --cov=observability --cov-report=html --cov-report=term

lint:
	ruff check observability/
	mypy observability/

format:
	black observability/ tests/
	isort observability/ tests/
	ruff check --fix observability/

run-ingestion:
	uvicorn observability.ingestion.main:app --reload --port 8000

run-query:
	uvicorn observability.api.main:app --reload --port 8001

run-agent-logs:
	python -m observability.agents.log_agent

run-agent-metrics:
	python -m observability.agents.metrics_agent

run-processor-logs:
	python -m observability.processing.log_processor

run-processor-metrics:
	python -m observability.processing.metrics_processor

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-rebuild:
	docker-compose up -d --build

# Kafka/Redpanda commands
kafka-up:
	@echo "Starting Redpanda (Kafka)..."
	docker-compose up -d redpanda console
	@echo "Waiting for Redpanda to be ready..."
	@sleep 5
	@echo "Redpanda started!"
	@echo "  - Kafka API: localhost:19092"
	@echo "  - Console UI: http://localhost:8080"

kafka-down:
	docker-compose stop redpanda console

kafka-init:
	@echo "Initializing Kafka topics..."
	./scripts/init_kafka_topics.sh

kafka-logs:
	docker logs -f observability-redpanda

kafka-topics:
	@echo "Listing Kafka topics:"
	docker exec observability-redpanda rpk topic list

kafka-consume-logs:
	@echo "Consuming from logs.raw topic (Ctrl+C to stop):"
	docker exec observability-redpanda rpk topic consume logs.raw --format json

kafka-consume-metrics:
	@echo "Consuming from metrics.raw topic (Ctrl+C to stop):"
	docker exec observability-redpanda rpk topic consume metrics.raw --format json