# AIVA — AI Virtual Assistant Platform

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A production-ready FastAPI backend that combines **LLM chat**, **Retrieval-Augmented Generation (RAG)**, background document processing, Redis caching, and Prometheus observability in a single deployable service.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [How to Run Locally](#how-to-run-locally)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Sample Requests & Responses](#sample-requests--responses)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Project Structure](#project-structure)

---

## Features

| Feature | Details |
|---------|---------|
| LLM Chat | OpenAI GPT with retry, timeout, and token tracking |
| RAG | Upload docs → auto-embed → semantic search → grounded answers |
| Background jobs | Celery + Redis: extract → chunk → embed → upsert to Qdrant |
| Caching | Redis cache for embeddings, AI responses, and FAQ queries |
| Auth & Rate limiting | API-key middleware + per-client rate limiting (60 req/min) |
| Observability | Structured JSON logs + Prometheus metrics at `/metrics` |
| Database | PostgreSQL (async SQLAlchemy) for document metadata |

---

## Architecture

```
                      ┌─────────────────────────────────────────┐
                      │              HTTP Clients               │
                      └──────────────────┬──────────────────────┘
                                         │
                      ┌──────────────────▼──────────────────────┐
                      │           Middleware Stack               │
                      │  RequestID → Logging → RateLimit → Auth  │
                      │         + PrometheusMiddleware           │
                      └──────────────────┬──────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                             │                               │
  ┌───────▼──────┐           ┌──────────▼──────────┐        ┌──────────▼──────┐
  │  /ai routes  │           │  /documents routes  │        │  /health routes  │
  └───────┬──────┘           └──────────┬──────────┘        └──────────────────┘
          │                             │
  ┌───────▼──────┐           ┌──────────▼──────────┐
  │  AI Service  │           │  Document Upload     │
  │  LangChain   │           │  → Celery Task       │
  └───────┬──────┘           └──────────┬──────────┘
          │                             │
  ┌───────▼──────┐    ┌─────────────────▼──────────────────────┐
  │   OpenAI     │    │  Worker: Extract → Chunk → Embed        │
  │   GPT API    │    └─────────────────┬──────────────────────┘
  └──────────────┘                      │
                              ┌─────────▼──────────────────────┐
                              │  Qdrant (vectors)               │
                              │  PostgreSQL (metadata)          │
                              │  Redis (cache + broker)         │
                              └─────────────────────────────────┘
```

### Request flow — RAG query

```
POST /documents/query
  1. RateLimitMiddleware  — check per-client quota
  2. APIKeyAuthMiddleware — validate X-API-Key header
  3. RAGService           — embed question via OpenAI
  4. Qdrant               — similarity search (top-k chunks)
  5. AIService            — build prompt with context + call GPT
  6. Response             — answer + source citations + confidence
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI 0.109, Uvicorn |
| AI / LLM | OpenAI GPT, LangChain 0.3 |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL 15 (async SQLAlchemy + asyncpg) |
| Cache / Broker | Redis 7 |
| Background jobs | Celery 5 + Flower (monitoring UI) |
| Observability | prometheus-client, python-json-logger |
| Migrations | Alembic |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Code quality | Black, isort, flake8, mypy |

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for infrastructure services)
- An [OpenAI API key](https://platform.openai.com/api-keys)

---

## How to Run Locally

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd ai_virtual_assistant_platform

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
make install-dev
# or: pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set the four required variables below
```

```env
OPENAI_API_KEY=sk-...
SECRET_KEY=change-me-to-a-32-char-random-string
API_KEY=your-client-api-key
DATABASE_URL=postgresql+asyncpg://aiva:aiva@localhost:5432/aiva
```

### 4. Start infrastructure services

```bash
make docker-up
# PostgreSQL :5432  Redis :6379  Qdrant :6333  Flower :5555
```

### 5. Run database migrations

```bash
make db-migrate
```

### 6. Start the API

```bash
make run
# API  → http://localhost:8000
# Docs → http://localhost:8000/docs
```

### 7. (Optional) Start the Celery worker

The worker is required for background document processing (upload → embed).

```bash
make celery-worker
```

### Full stack via Docker Compose

```bash
docker compose up -d        # start everything
docker compose logs -f      # tail logs
docker compose down         # stop
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key |
| `SECRET_KEY` | **Yes** | — | App secret (>= 32 chars) |
| `API_KEY` | **Yes** | — | Value for `X-API-Key` header |
| `DATABASE_URL` | **Yes** | — | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `QDRANT_HOST` | No | `localhost` | Qdrant host |
| `QDRANT_PORT` | No | `6333` | Qdrant gRPC port |
| `OPENAI_MODEL` | No | `gpt-3.5-turbo` | Default LLM model |
| `OPENAI_MAX_TOKENS` | No | `2000` | Max tokens per response |
| `OPENAI_TEMPERATURE` | No | `0.7` | Sampling temperature (0-2) |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | Requests/minute per client |
| `CACHE_ENABLED` | No | `true` | Enable Redis caching |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_FORMAT` | No | `json` | `json` (production) or `text` (development) |
| `APP_ENV` | No | `development` | `development` / `staging` / `production` |

See [.env.example](.env.example) for the full list.

---

## API Reference

All endpoints except `/health*`, `/metrics`, `/docs`, and `/redoc` require:

```
X-API-Key: <your-api-key>
```

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI) and **`/redoc`**.

### Health & Observability

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Basic liveness (name, version, uptime) |
| GET | `/health/detailed` | No | Component status (config, features) |
| GET | `/health/ready` | No | Kubernetes readiness probe |
| GET | `/health/live` | No | Kubernetes liveness probe |
| GET | `/health/cache-stats` | No | Cache hit/miss counters |
| GET | `/metrics` | No | Prometheus scrape endpoint |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/documents/upload` | Upload file (PDF/DOCX/TXT/HTML/MD, max 10 MB) |
| GET | `/documents/` | List documents (pagination + status/type filters) |
| GET | `/documents/{id}` | Fetch document metadata |
| DELETE | `/documents/{id}` | Delete record + Qdrant vectors + file |
| GET | `/documents/tasks/{task_id}` | Poll background processing status |
| POST | `/documents/search` | Semantic similarity search |
| POST | `/documents/query` | RAG: answer a question from documents |
| GET | `/documents/stats/overview` | Aggregate counts and sizes |

### AI (direct LLM)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ai/chat` | Chat completion |
| POST | `/ai/completion` | Text completion |
| GET | `/ai/models` | List available models |

---

## Sample Requests & Responses

### Upload a document

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "X-API-Key: your-api-key" \
  -F "file=@report.pdf"
```

```json
{
  "id": 1,
  "filename": "report.pdf",
  "file_type": "pdf",
  "file_size": 204800,
  "status": "pending",
  "message": "Document uploaded. Processing started (task: a3f1b2c4...)"
}
```

### Poll background task

```bash
curl http://localhost:8000/documents/tasks/a3f1b2c4-... \
  -H "X-API-Key: your-api-key"
```

```json
{
  "task_id": "a3f1b2c4-...",
  "state": "SUCCESS",
  "status": "Task completed successfully",
  "result": { "chunks_created": 42 }
}
```

### Semantic search

```bash
curl -X POST http://localhost:8000/documents/search \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "quarterly revenue targets", "limit": 5, "min_score": 0.7}'
```

```json
{
  "query": "quarterly revenue targets",
  "results": [
    {
      "chunk_id": "abc123",
      "document_id": 1,
      "filename": "report.pdf",
      "content": "Q3 revenue target is $4.2M representing 12% YoY growth...",
      "score": 0.92,
      "metadata": { "page": 3 }
    }
  ],
  "total_results": 1
}
```

### RAG — ask a question

```bash
curl -X POST http://localhost:8000/documents/query \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the Q3 revenue target?", "top_k": 5, "min_score": 0.7}'
```

```json
{
  "question": "What was the Q3 revenue target?",
  "answer": "Based on the provided documents, the Q3 revenue target was $4.2M, representing 12% year-over-year growth.",
  "sources": [
    {
      "chunk_id": "abc123",
      "document_id": 1,
      "filename": "report.pdf",
      "content": "Q3 revenue target is $4.2M...",
      "score": 0.92,
      "page": 3
    }
  ],
  "confidence": 0.92,
  "total_chunks_searched": 5
}
```

---

## Testing

```bash
make test              # all tests
make test-unit         # unit tests only
make test-integration  # integration tests only
make test-cov          # with HTML coverage report → htmlcov/
make test-cov-check    # fail if coverage < 65%
```

Run a single file:

```bash
pytest tests/unit/test_rag_service.py -v
```

---

## Monitoring

### Logs

Structured JSON logs go to `./logs/aiva.log` and stdout.

```bash
docker compose logs -f aiva
```

Key log fields: `timestamp`, `level`, `request_id`, `duration_ms`, `model`, `tokens_used`, `cost_usd`.

### Prometheus

Metrics available at `GET /metrics` (no auth required). Scrape config:

```yaml
scrape_configs:
  - job_name: aiva
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: /metrics
```

Key metrics: `aiva_http_requests_total`, `aiva_http_request_duration_seconds`,
`aiva_llm_tokens_total`, `aiva_llm_cost_dollars_total`.
See [docs/alerting_rules.md](docs/alerting_rules.md) for alert rules and Grafana queries.

### Flower (Celery monitor)

`http://localhost:5555`

---

## Project Structure

```
.
├── app/
│   ├── api/routes/         # FastAPI routers (health, ai, documents, auth)
│   ├── core/               # Config, middleware, exceptions, logging
│   ├── db/                 # Async DB session
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/
│   │   ├── ai_service.py           # LLM orchestration
│   │   ├── rag_service.py          # RAG pipeline
│   │   ├── embedding_service.py    # OpenAI embeddings
│   │   ├── vector_store.py         # Qdrant wrapper
│   │   ├── search_service.py       # Semantic search
│   │   ├── cache_service.py        # Redis cache
│   │   ├── text_chunker.py         # Token-aware chunking (tiktoken)
│   │   ├── token_tracker.py        # Token usage & cost tracking
│   │   ├── metrics_service.py      # Prometheus metric definitions
│   │   └── extractors/             # PDF, DOCX, TXT, HTML, MD extractors
│   ├── tasks/              # Celery background tasks
│   └── utils/              # Retry decorator, logging helpers
├── alembic/                # DB migrations
├── docs/                   # Architecture notes, alerting rules
├── scripts/                # Setup and demo scripts
├── tests/
│   ├── unit/
│   └── integration/
├── docker-compose.yaml
├── Dockerfile              # API image
├── Dockerfile.celery       # Worker image
├── Makefile
└── requirements.txt
```
