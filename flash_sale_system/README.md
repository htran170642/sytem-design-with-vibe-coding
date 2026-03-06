# Flash Sale System — System Design Overview

A high-concurrency flash sale system designed to handle 100k+ concurrent requests with atomic stock control, idempotent order processing, and queue-based eventual consistency.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Architecture Overview](#architecture-overview)
- [Component Design](#component-design)
- [Data Flow](#data-flow)
- [Key Design Decisions](#key-design-decisions)
- [Tradeoffs and Assumptions](#tradeoffs-and-assumptions)
- [Failure Scenarios](#failure-scenarios)
- [Scalability](#scalability)

---

## Problem Statement

During a flash sale, thousands of users simultaneously attempt to purchase a limited-stock product. The system must:

- Prevent overselling (stock never goes below 0)
- Ensure each user buys at most once
- Return a response quickly under extreme load (P99 < 50ms)
- Survive worker crashes without data loss or duplicate orders
- Scale horizontally as demand grows

---

## Architecture Overview

```
                          ┌─────────────────────────────────────────────────┐
                          │                   API Layer                     │
  ┌────────┐  POST /buy   │  ┌─────────────────────────────────────────┐    │
  │ Client │─────────────▶│  │  FastAPI (async)                        │    │
  └────────┘              │  │                                         │    │
                          │  │  1. Validate request (Pydantic)         │    │
                          │  │  2. Rate limit check (token bucket)     │    │
                          │  │  3. Idempotency check  ─────────────────┼────┼───┐
                          │  │  4. Atomic stock decrement ─────────────┼────┼───┤
                          │  │  5. Enqueue order event ────────────────┼────┼───┤
                          │  │  6. Return 200 / 409 / 410              │    │   │
                          │  └─────────────────────────────────────────┘    │   │
                          └─────────────────────────────────────────────────┘   │
                                                                                │
                          ┌─────────────────────────────────────────────────┐   │
                          │                  Redis Layer                    │   │
                          │                                                 │◀──┘
                          │  ┌──────────────────┐  ┌────────────────────┐   │
                          │  │ Idempotency Keys │  │   Stock Counter    │   │
                          │  │ SET NX EX {ttl}  │  │  (Lua script decr) │   │
                          │  └──────────────────┘  └────────────────────┘   │
                          │                                                 │
                          │  ┌──────────────────────────────────────────┐   │
                          │  │         Redis Streams (orders)           │   │
                          │  │  XADD → consumer group → worker reads    │   │
                          │  └──────────────────────────────────────────┘   │
                          └─────────────────────────────────────────────────┘
                                              │ XREAD (consumer group)
                          ┌───────────────────▼─────────────────────────────┐
                          │               Worker Layer                      │
                          │                                                 │
                          │  1. Read message from Redis Stream              │
                          │  2. Deserialize order event                     │
                          │  3. INSERT into PostgreSQL (idempotent)         │
                          │  4. XACK message only after successful write    │
                          │  5. Retry with exponential backoff on failure   │
                          │  6. Dead-letter queue for persistent failures   │
                          └─────────────────────┬───────────────────────────┘
                                                │
                          ┌─────────────────────▼───────────────────────────┐
                          │              PostgreSQL (orders table)          │
                          │                                                 │
                          │  UNIQUE(user_id, product_id) — idempotency      │
                          │  UUID primary key, status enum, timestamps      │
                          └─────────────────────────────────────────────────┘
```

---

## Component Design

### API Service (FastAPI)

- **Async I/O** throughout — no blocking calls on the hot path
- **Middleware**: Request ID injection, structured JSON logging, Prometheus metrics
- **Health check** endpoint for load balancer probes
- **Stateless** — horizontally scalable behind a load balancer

Critical path for `POST /buy` (all Redis, no DB):

```
Request
  → Pydantic validation
  → Rate limit check (Redis, token bucket)
  → Idempotency check (Redis SET NX)
  → Lua stock decrement (atomic)
  → XADD to Redis Stream
  → Return response
```

### Redis Layer

**Stock management**: A single Redis key per product holds the stock count. A Lua script atomically checks and decrements:

```lua
local stock = redis.call('GET', KEYS[1])
if tonumber(stock) <= 0 then return 0 end
redis.call('DECR', KEYS[1])
return 1
```

This guarantees no race conditions — Redis is single-threaded for command execution and Lua scripts are atomic.

**Idempotency keys**: `SET idempotency:{key} "processing" NX EX 86400` — if the key already exists, the request is a duplicate and returns the cached status.

**Redis Streams**: `XADD orders * user_id {u} product_id {p} idempotency_key {k} timestamp {t}` — provides durable, ordered event log with consumer group semantics (at-least-once delivery).

**Persistence**: AOF (Append-Only File) enabled to survive Redis restarts without losing stock or stream data.

### Worker Service

- Reads from Redis Stream using consumer groups (`XREADGROUP`)
- Writes to PostgreSQL with idempotent INSERT (conflict on `UNIQUE(user_id, product_id)` is treated as success, not error)
- **Only XACK after successful DB write** — guarantees at-least-once processing
- On crash/restart, unacked messages are redelivered automatically
- Exponential backoff on transient failures
- Persistent failures route to a dead-letter queue (separate stream)

### PostgreSQL

```sql
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'failed');

CREATE TABLE orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    product_id  TEXT NOT NULL,
    status      order_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, product_id)
);

CREATE INDEX idx_orders_product_id ON orders(product_id);
CREATE INDEX idx_orders_user_id    ON orders(user_id);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

---

## Data Flow

### Happy Path

```
1. Client sends POST /buy {user_id, product_id, idempotency_key}
2. API validates request schema
3. API checks rate limit — OK
4. API: SET idempotency:{key} NX → success (new request)
5. API: Lua script decrements stock → returns 1 (success)
6. API: XADD orders stream → message enqueued
7. API: returns HTTP 200 {"status": "accepted"}
8. Worker: XREADGROUP picks up message
9. Worker: INSERT INTO orders → success
10. Worker: XACK message
```

### Out-of-Stock Path

```
5. Lua script: stock == 0 → returns 0
6. API: returns HTTP 410 {"error": "out_of_stock"}
   (idempotency key is deleted or marked sold-out)
```

### Duplicate Request Path

```
4. SET idempotency:{key} NX → fails (key exists)
5. API: returns HTTP 409 {"status": "duplicate"}
   (no stock touched, no stream write)
```

---

## Key Design Decisions

### Why Redis for stock instead of database?

Database row-level locking under 100k concurrent requests would cause lock contention, connection pool exhaustion, and latency spikes. Redis single-threaded execution + Lua atomicity eliminates contention entirely. The hot path never touches PostgreSQL.

### Why Redis Streams instead of Kafka/RabbitMQ?

Redis Streams provide consumer group semantics (at-least-once delivery, message acknowledgement, pending message tracking) with zero additional infrastructure. For a flash sale with a finite burst, Redis Streams are sufficient and operationally simpler. Kafka would be warranted at multi-million RPS or if replay across multiple consumers were needed.

### Why eventual consistency?

Synchronous DB writes on the critical path would cap throughput at DB insert rate (~10k/s with connection pooling). By decoupling via Redis Streams, the API can accept orders at Redis throughput (~100k+/s) and the worker catches up asynchronously. The user gets an "accepted" response — the order is guaranteed to be written eventually unless both Redis and the worker die simultaneously with no persistence.

### Why Lua for stock decrement?

Lua scripts in Redis execute atomically — no other command runs between the check and decrement. The alternative (`GET` then `SET`) has a TOCTOU race condition: two requests could both read `stock=1`, both decrement, and result in `stock=-1` (oversell). Lua prevents this completely.

### Why `UNIQUE(user_id, product_id)` in addition to Redis idempotency?

Defence in depth. The Redis idempotency key has a TTL and can expire. The database constraint is permanent and provides a hard guarantee even if Redis data is lost or the idempotency key expires before the worker processes the message.

---

## Tradeoffs and Assumptions

### Tradeoffs

| Decision | Benefit | Cost |
|---|---|---|
| Redis stock (not DB) | Zero lock contention, ~100k RPS | Redis restart risk (mitigated by AOF) |
| Eventual consistency | High throughput, fast response | User sees "accepted" before DB write |
| At-least-once delivery | No message loss on crash | Worker must handle duplicate inserts |
| Redis Streams (not Kafka) | Simpler ops, zero extra infra | Less replay flexibility, single-node limit |
| Stateless API | Horizontal scalability | Session state must live in Redis |
| Single Redis node (Phase 1–9) | Simpler setup | Single point of failure for stock |

### Assumptions

1. **Flash sale duration is short** — stock depletes in seconds/minutes, not days. Redis memory and stream size are not concerns.
2. **Each product has one stock pool** — no per-warehouse or per-region inventory splitting (stock sharding is a Phase 3 optional enhancement).
3. **User identity is provided in the request** — JWT authentication is added in Phase 9; initial phases trust `user_id` in the request body.
4. **Network between API and Redis is reliable** — API retries Redis operations on transient errors but does not assume Redis is unavailable.
5. **PostgreSQL can handle the sustained worker write rate** — worker processes messages sequentially per consumer; throughput can be scaled by adding worker instances with separate consumer group members.
6. **Idempotency key TTL (24h) is sufficient** — users retrying a flash sale purchase within 24 hours will get the cached result; after 24h, duplicate protection falls back to the DB UNIQUE constraint.

---

## Failure Scenarios

### Redis crashes mid-sale

- With AOF persistence: Redis restarts and replays the log — stock and stream data recovered
- Orders already enqueued in the stream are preserved
- In-flight Lua scripts that did not complete: the stock decrement did not happen (atomic), so no oversell

### Worker crashes mid-processing

- Message was not XACK'd — Redis redelivers it to the next worker on reconnect
- Worker inserts into DB: if already inserted (duplicate), the UNIQUE constraint conflict is handled as success
- Result: at-least-once processing with idempotent writes — no data loss, no duplicates in DB

### API pod crashes after Lua decrement but before XADD

- Stock was decremented, but no order event was written to the stream
- The idempotency key was set, so retries return 409 (duplicate)
- **Result**: stock is lost for that slot — this is a known gap. Mitigation: use a Lua script that atomically decrements AND writes to the stream (MULTI/EXEC or a more complex Lua script). Not implemented in initial phases.

### DB is slow / unavailable

- Worker retries with exponential backoff
- Messages accumulate in Redis Stream (bounded by Redis memory)
- API is unaffected — critical path is Redis-only
- After max retries, message goes to DLQ for manual intervention

---

## Scalability

### Horizontal API scaling

The API is stateless. Add more instances behind a load balancer. All shared state lives in Redis.

### Increasing worker throughput

Add more consumer group members reading from the same stream. Redis Streams distribute messages across consumers automatically.

### Redis capacity

- Single node: ~100k ops/s, sufficient for flash sale bursts
- Phase 3 optional: stock sharding across multiple Redis keys (e.g., by product shard) to distribute load
- Production: Redis Cluster or a Redis replica for read offloading

### PostgreSQL capacity

- Connection pooling via PgBouncer (Phase 5 optimization)
- Partitioning orders by `created_at` for large datasets
- Read replicas for analytics queries
