# Phase 2 Complete — API Service (FastAPI)

## What was built

### File structure

```
api/
├── __init__.py
├── main.py              # FastAPI app + lifespan
├── dependencies.py      # Async Redis connection pool
├── schemas.py           # Pydantic request/response models
├── redis_ops.py         # Atomic Redis operations (Lua + Streams)
├── rate_limiter.py      # Token bucket + global counter (Lua)
├── circuit_breaker.py   # In-process circuit breaker
├── middleware/
│   ├── __init__.py
│   └── request_id.py    # X-Request-ID propagation
└── routes/
    ├── __init__.py
    ├── health.py        # GET /health
    └── buy.py           # POST /buy

shared/
└── logging.py           # structlog JSON configuration
```

---

## Step-by-step decisions

### Step 1 — FastAPI app (`api/main.py`)
- `lifespan` context manager: initialises Redis pool on startup, drains it on shutdown
- Middleware and routers registered after app creation

### Step 2 — Redis connection pool (`api/dependencies.py`)
- Module-level `ConnectionPool` with `max_connections=50`
- `RedisDep` Annotated alias keeps route signatures clean
- `decode_responses=True` so all values come back as `str`

### Step 3 — Structured logging (`shared/logging.py`)
- `structlog` with JSON renderer
- `merge_contextvars` processor so `request_id` bound by middleware appears in every log line automatically
- Log level driven by `settings.log_level`

### Step 4 — Request ID middleware (`api/middleware/request_id.py`)
- Accepts incoming `X-Request-ID` or generates a UUID
- Binds `request_id` into structlog context vars — automatically included in all downstream log lines
- Echoes the ID back in the response header

### Step 5 — Health check (`api/routes/health.py`)
- `GET /health` pings Redis and reports status
- Returns `{"status": "ok", "redis": "ok"|"unavailable"}`

### Step 6 — Pydantic schemas (`api/schemas.py`)
- `BuyRequest`: `user_id`, `product_id`, `idempotency_key` — all required strings with length bounds
- `BuyResponse`: `status` + optional `order_id` + `message`
- Status values: `accepted`, `duplicate`, `sold_out`, `rate_limited`

### Step 7 — Idempotency (`api/redis_ops.py`)
- Key format: `idempotency:<idempotency_key>`
- `check_idempotency`: plain `GET` — returns stored `order_id` or `None`
- `set_idempotency`: `SET … EX <ttl>` — written **after** successful enqueue only
- TTL controlled by `settings.idempotency_ttl_seconds` (default 24 h)

### Step 8 — Atomic Lua stock decrement + Redis Stream (`api/redis_ops.py`)
- `decrement_stock`: Lua script does `GET → check → DECR` atomically; returns `1` (ok), `0` (sold out), `-1` (key missing)
- `enqueue_order`: `XADD orders * order_id … user_id … product_id …`
- Stream name from `settings.orders_stream`

### Step 9 — Rate limiters (`api/rate_limiter.py`)
- **Per-user**: `INCR rl:user:<user_id>` + `EXPIRE 1` on first hit; limit from `settings.rate_limit_per_user`
- **Global**: `INCR rl:global:<epoch_second>` + `EXPIRE 1`; limit from `settings.rate_limit_global`
- Both implemented as Lua scripts to avoid TOCTOU race between INCR and EXPIRE

### Step 10 — Circuit breaker (`api/circuit_breaker.py`)
- Three-state machine: `CLOSED → OPEN → HALF_OPEN → CLOSED`
- Opens after `failure_threshold` (5) consecutive Redis errors
- Auto-transitions to `HALF_OPEN` after `recovery_timeout` (10 s)
- Returns HTTP 503 while open; success resets failure count

---

## Request flow for `POST /buy`

```
Client
  │
  ▼
RequestIDMiddleware        bind request_id to log context
  │
  ▼
buy()
  ├─ CircuitBreaker.is_open?  →  503 if open
  ├─ RateLimiter.allow_user   →  429 if exceeded
  ├─ RateLimiter.allow_global →  429 if exceeded
  ├─ check_idempotency        →  200 "duplicate" if seen
  ├─ decrement_stock (Lua)    →  200 "sold_out" if 0
  ├─ enqueue_order (XADD)
  ├─ set_idempotency
  └─ 200 "accepted"
```

---

## Critical constraints honoured

| Constraint | How |
|---|---|
| No overselling | Lua script: single atomic read-check-decrement |
| One purchase per user | Idempotency key checked before decrement |
| P99 < 50ms hot path | Redis-only; no DB calls |
| Crash safety | Idempotency key set **after** stream enqueue |
