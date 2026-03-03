# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup

```bash
python3 -m venv venv && source venv/bin/activate
make install-dev        # install all dependencies (prod + dev)
cp .env.example .env    # configure OPENAI_API_KEY, SECRET_KEY, API_KEY, DATABASE_URL
```

### Run

```bash
make run                # start FastAPI with hot reload (http://localhost:8000)
make docker-up          # start Redis, PostgreSQL, Qdrant, Flower via docker-compose
make celery-worker      # start Celery worker for background document processing
```

### Test

```bash
make test               # run all tests
make test-cov           # run tests with HTML coverage report (htmlcov/)
make test-unit          # unit tests only (tests/unit/)
make test-integration   # integration tests only (tests/integration/)
# Run a single test file:
pytest tests/unit/test_rag_service.py -v
```

### Lint & Format

```bash
make format             # format with black (line-length 100) + isort
make format-check       # check formatting without writing changes
make lint               # run flake8 + mypy + pylint
```

### Database

```bash
make db-migrate                        # apply migrations (alembic upgrade head)
make db-revision message="..."         # create a new migration
```

## Architecture

AIVA is a layered FastAPI backend. The request flow is:

```
HTTP → Middleware stack → Route handler → Service layer → External APIs / DB
```

### Middleware stack ([app/core/middleware.py](app/core/middleware.py))

Applied in order: RequestIDMiddleware → RequestLoggingMiddleware → RateLimitMiddleware → APIKeyAuthMiddleware. Every response carries `X-Request-ID` and `X-Process-Time` headers.

### API routes ([app/api/routes/](app/api/routes/))

- `health.py` — liveness/readiness
- `ai.py` — `/ai/chat`, `/ai/completion`, `/ai/models`
- `documents.py` — `/documents/upload`, `/documents/search`, `/documents/query`
- `auth.py` — API key validation

### Services ([app/services/](app/services/))

- `rag_service.py` — orchestrates the full RAG pipeline (search + LLM answer)
- `vector_store.py` — Qdrant wrapper (upsert, search, delete)
- `embedding_service.py` — OpenAI `text-embedding-3-small` (1536 dims)
- `text_chunker.py` — token-aware chunking via tiktoken (500 tokens, 200 overlap)
- `ai_service.py` — OpenAI chat/completion with retry logic
- `langchain_service.py` — LangChain integration
- `extractors/` — per-format text extractors (PDF, DOCX, TXT, HTML, MD)

### Background jobs ([app/tasks/](app/tasks/))

`document_tasks.py` runs via Celery (Redis broker): extract → chunk → embed → upsert to Qdrant. Triggered automatically on document upload.

### Configuration ([app/core/config.py](app/core/config.py))

Pydantic `Settings` class. All tunable values come from environment variables; [.env.example](.env.example) documents every key.

### Key environment variables

| Variable                      | Purpose                             |
| ----------------------------- | ----------------------------------- |
| `OPENAI_API_KEY`              | Required for all AI/embedding calls |
| `SECRET_KEY` / `API_KEY`      | App security                        |
| `DATABASE_URL`                | PostgreSQL (asyncpg driver)         |
| `REDIS_URL`                   | Celery broker + cache               |
| `QDRANT_HOST` / `QDRANT_PORT` | Vector DB                           |

### External services ([docker-compose.yaml](docker-compose.yaml))

Redis 7 (6379), PostgreSQL 15 (5432), Qdrant (6333/6334), Flower (5555).

### Code standards

- Black, line-length 100
- isort with `profile = black`
- MyPy gradual typing (not strict)
- Python 3.11+

## Development Progress

See [TODO.md](TODO.md) for the phase-by-phase roadmap and current progress. Always check it before starting new work to understand what's done and what's next.
Do a single step at a time for each phase. Move to next step when required.
After finish any step, please mark it done to [TODO.md](TODO.md)
