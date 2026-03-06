# Phase 11 — Testing: Complete

## Summary

Phase 11 adds a comprehensive test suite covering every layer of the flash sale system: pure unit tests (no external dependencies), integration tests with real Redis, integration tests with real PostgreSQL, and end-to-end tests that exercise the full pipeline from API call to DB row.

## New Test Files

### Unit Tests (`tests/`)

| File | What it covers |
|---|---|
| `test_stream_schema.py` | `OrderEvent.create()`, `from_dict()`, `to_dict()`, immutability, schema version |
| `test_retry.py` | `_backoff_delay` math, `with_retry` success/transient/permanent/exhausted paths |
| `test_consumer.py` | `StreamConsumer.ack()`, `_read_new()`, `_reclaim_stale()` with mocked Redis |
| `test_dlq.py` | `send_to_dlq()` — XADD/XACK order, field presence, 500-char error cap |

### Integration Tests — Redis only (`tests/integration/`)

| File | What it covers |
|---|---|
| `test_lua_script.py` | Lua decrement script returns (1/0/-1), stock never goes negative, concurrent no-oversell, EVALSHA via `LuaScripts` |

### Integration Tests — PostgreSQL (`tests/integration/`)

| File | What it covers |
|---|---|
| `test_worker_db.py` | `insert_order()` first insert, duplicate (ON CONFLICT), field storage, concurrent no-duplicate rows |

### Integration Tests — End-to-End (`tests/integration/`)

| File | What it covers |
|---|---|
| `test_e2e.py` | Full pipeline: POST /buy → Redis stock decrement → Stream → Worker → DB insert; idempotency across all layers; concurrent no-oversell |

## Infrastructure Changes

**`tests/integration/conftest.py`** — extended with:
- `pg_pool` fixture: async asyncpg pool, skips if PostgreSQL unavailable, wipes `orders` table before/after each test
- `PG_TEST_URL` env var support (default: `postgresql://flash_sale:flash_sale@localhost:5432/flash_sale`)

## Coverage Configuration

Already configured in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov=api --cov=worker --cov=shared --cov-report=term-missing"
```

Run with HTML report:
```bash
pytest --cov=api --cov=worker --cov=shared --cov-report=html
```

## Running Tests

```bash
# Unit tests only (no Redis/PostgreSQL required)
pytest tests/ --ignore=tests/integration -v

# Integration tests — Redis only (requires redis://localhost:6379)
pytest tests/integration/test_lua_script.py tests/integration/test_api_integration.py -v

# Integration tests — PostgreSQL (requires running PostgreSQL + init.sql applied)
pytest tests/integration/test_worker_db.py tests/integration/test_e2e.py -v

# All tests
pytest -v

# With custom URLs
REDIS_TEST_URL=redis://myredis:6379/15 PG_TEST_URL=postgresql://user:pass@mydb/flash_sale pytest -v
```

## Test Counts

| Category | Files | Tests (approx) |
|---|---|---|
| Unit — existing (phases 1–10) | 5 | ~70 |
| Unit — new (phase 11) | 4 | ~50 |
| Integration — Redis | 2 | ~35 |
| Integration — PostgreSQL | 1 | ~12 |
| Integration — E2E | 1 | ~8 |
| **Total** | **13** | **~175** |

## Key Design Decisions

- **PostgreSQL tests skip gracefully** — `pg_pool` fixture calls `pytest.skip()` if the DB is unreachable or the schema is missing, keeping CI fast when only Redis is available.
- **Test pool injected via `worker.db._pool`** — avoids calling `init_db_pool()` with production settings during tests; the module-level `_pool` is overridden and reset after each test.
- **E2E stream drain helper** — `_drain_stream_to_db()` creates a consumer group and processes pending messages, fully simulating the worker without running it as a separate process.
- **Concurrent tests use `asyncio.gather()`** — truly concurrent within the single-process event loop, surfacing race conditions that sequential tests would miss.
