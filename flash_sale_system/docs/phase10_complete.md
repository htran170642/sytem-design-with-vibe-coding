# Phase 10 Complete — Infrastructure

## Files Created

| File | Purpose |
|---|---|
| `Dockerfile.api` | 2-stage build — API service (uvicorn, 4 workers) |
| `Dockerfile.worker` | 2-stage build — Stream consumer worker |
| `docker-compose.yml` | Full local stack: redis, postgres, api, worker |
| `docker-compose.prod.yml` | Production overrides (resource limits, no exposed ports, replicas) |
| `.env.docker` | Non-secret defaults for docker-compose |
| `Makefile` | Developer shortcuts for all common tasks |

---

## Docker Images

Both images use a 2-stage build (`python:3.12-slim`):
- **Stage 1 (builder):** Poetry exports deps → pip installs to `/install`
- **Stage 2 (runtime):** Copy deps + source only — no Poetry, no dev tools

| Image | Size |
|---|---|
| `flash-sale-api:local` | 175MB |
| `flash-sale-worker:local` | 175MB |

---

## docker-compose Service Graph

```
redis ──┐
        ├── api (healthcheck) ──── worker
postgres┘
```

All `depends_on` use `condition: service_healthy` — no race conditions on startup.

### Local dev
```bash
make up          # start full stack
make logs        # tail all logs
make down        # stop everything
```

### Scale workers
```bash
docker compose up --scale worker=3
# Each replica should set WORKER_CONSUMER_NAME to a unique value
```

---

## Production Profile

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

| Change from dev | Value |
|---|---|
| Redis/Postgres ports | Not exposed (internal network only) |
| Log level | WARNING |
| API workers | 8 |
| Worker replicas | 2 |
| Resource limits | CPU + memory per service |
| Restart policy | `on-failure`, max 3 attempts |

---

## Makefile Targets

```
make help          # list all targets
make dev           # uvicorn with hot-reload
make test          # pytest
make load          # Locust 1k users 30s
make test-crash    # failure injection: worker crash
make migrate       # alembic upgrade head
make lint          # ruff check
make build         # docker build both images
```
