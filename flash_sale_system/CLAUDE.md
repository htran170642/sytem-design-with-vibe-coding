# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A high-concurrency flash sale system designed to handle 100k concurrent requests with atomic stock control, idempotent order processing, and queue-based eventual consistency. Currently in the planning/implementation phase — see [TODO.md](TODO.md) for the full phased roadmap.

## Planned Architecture

```
flash-sale/
├── api/           # FastAPI service — handles POST /buy, rate limiting, idempotency
├── worker/        # Stream consumer — reads Redis Streams, writes to PostgreSQL
├── shared/        # Shared utilities, models, config
├── infrastructure/# Docker, k8s manifests, Redis/PostgreSQL init scripts
└── tests/         # Unit and integration tests
```

### Component Interaction

```
Client → FastAPI (api/)
            → Redis: idempotency key check (SET NX)
            → Redis: atomic Lua stock decrement
            → Redis Streams: XADD order event
         → return 200/409/sold-out immediately

Redis Streams → Worker (worker/)
                    → PostgreSQL: INSERT INTO orders (idempotent via UNIQUE constraint)
                    → Redis: XACK message
```

## Technology Stack

- **API**: FastAPI (async), Pydantic for request validation
- **Queue**: Redis Streams with consumer groups
- **Cache / Stock**: Redis (Lua scripts for atomic operations)
- **Database**: PostgreSQL with asyncpg or psycopg3
- **Observability**: Prometheus metrics, structured JSON logging, correlation IDs
- **Load testing**: Locust
- **Tooling**: Poetry, Ruff, strict MyPy, pre-commit hooks

## Key Design Patterns

### Atomic Stock Decrement (Lua)
Stock is managed in Redis with a Lua script to guarantee atomicity — no database locking. Script decrements only if `stock > 0`, returns 0 on out-of-stock.

### Idempotency
- API layer: `SET idempotency:{key} NX EX {ttl}` before processing
- Database layer: `UNIQUE(user_id, product_id)` constraint on `orders` table
- Worker handles duplicate insert errors safely (not a failure)

### Eventual Consistency Model
API returns success as soon as the order is enqueued in Redis Streams. The worker processes asynchronously and writes to PostgreSQL. No distributed transaction — idempotency at both layers prevents duplicates.

### Rate Limiting
Per-user token bucket + global rate limiter in the API layer. Per-IP throttling in the security layer (Phase 9).

## Implementation Phases

Follow [TODO.md](TODO.md) phase order strictly:
1. **Phase 1** — Project setup (Poetry, MyPy, Ruff, pre-commit, .env)
2. **Phase 2** — FastAPI app with `POST /buy`, idempotency, rate limiting
3. **Phase 3** — Redis Lua scripts, Streams, AOF persistence
4. **Phase 4** — Worker service with retry/DLQ/graceful shutdown
5. **Phase 5** — PostgreSQL schema and migrations
6. **Phase 6** — Prometheus metrics + structured logging
7. **Phase 7** — Locust load testing (10k concurrent users)
8. **Phase 8** — Failure injection testing
9. **Phase 9** — JWT auth, bot detection, per-IP throttling
10. **Phase 10** — Docker + docker-compose + Makefile
11. **Phase 11** — Unit and integration tests with coverage

Always check it before starting new work to understand what's done and what's next.
Do a single step at a time for each phase. Move to next step when required.
After finish any step, please mark it done to [TODO.md](TODO.md)
Finally, create complete file md for each phase, for example phase1_complete.md

## Critical Constraints

- **No overselling**: Stock decrement must be atomic (Lua script in Redis). Never use `GET` + `SET` for stock.
- **One purchase per user**: Enforced by both Redis idempotency key AND `UNIQUE(user_id, product_id)` DB constraint.
- **Worker crash safety**: Worker must only `XACK` after successful DB write. On restart, unacked messages are redelivered.
- **P99 latency < 50ms**: All hot path operations must be Redis-only (no DB on the critical path).
