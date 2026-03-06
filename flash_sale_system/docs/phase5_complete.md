# Phase 5 Complete — PostgreSQL Design

## Files Created / Modified

| File | Purpose |
|---|---|
| `infrastructure/postgres/init.sql` | Schema (created in Phase 4, finalized here) |
| `alembic/env.py` | Configured to read `DATABASE_URL` from `settings` |
| `alembic/versions/0001_create_orders_table.py` | Baseline migration — creates table, enum, indexes |
| `infrastructure/scripts/benchmark_insert.py` | Insert throughput benchmark |

---

## Schema

```sql
CREATE TYPE order_status AS ENUM ('fulfilled', 'failed');

CREATE TABLE orders (
    id          BIGSERIAL PRIMARY KEY,
    order_id    UUID         NOT NULL,
    user_id     TEXT         NOT NULL,
    product_id  TEXT         NOT NULL,
    status      order_status NOT NULL DEFAULT 'fulfilled',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_product UNIQUE (user_id, product_id)
);

CREATE INDEX idx_orders_order_id   ON orders (order_id);
CREATE INDEX idx_orders_product_id ON orders (product_id);
CREATE INDEX idx_orders_user_id    ON orders (user_id);
CREATE INDEX idx_orders_created_at ON orders (created_at);
```

---

## Migrations

Alembic initialized with `sqlalchemy.url` wired from `settings.database_url`.

```
<base> -> 0001 (head), create_orders_table
```

Run migrations: `python3 -m alembic upgrade head`

---

## Connection Pooling

`worker/db.py` uses `asyncpg.create_pool` (min=2, max=10, command_timeout=10s).
Pool is initialized once at worker startup and drained on graceful shutdown.

---

## Benchmark Results

| Scenario | Rows/sec |
|---|---|
| Sequential (100 rows) | ~443 |
| Concurrent 500 tasks | ~1,379 |
| Concurrent 1000 tasks | ~2,487 |

Concurrency gives ~5× improvement over sequential. Pool saturates at 10 connections.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `UNIQUE(user_id, product_id)` | Ultimate source of truth for one-purchase-per-user |
| `ON CONFLICT DO NOTHING` | Idempotent inserts without exceptions — cleaner than catching `UniqueViolationError` |
| `TIMESTAMPTZ` for `created_at` | Timezone-aware — safe for multi-region |
| Alembic over raw SQL | Versioned, reversible, trackable schema changes |
| asyncpg over psycopg | Faster binary protocol, native `asyncio` support |
