# Phase 3 Complete — Redis Layer

## Summary

All Redis layer components are implemented, tested, and verified.

---

## Stock Management

| File | Purpose |
|---|---|
| `infrastructure/scripts/preload_stock.py` | Seed `stock:{id}` and `stock_initial:{id}` before sale |
| `infrastructure/redis/decrement_stock.lua` | Standalone Lua script — atomic GET+DECR |
| `shared/lua_scripts.py` | Loads scripts via `SCRIPT LOAD`, calls via `EVALSHA` |
| `infrastructure/scripts/test_no_oversell.py` | 500 concurrent decrements, stock=100 → exactly 100 succeed |
| `infrastructure/scripts/reconcile_stock.py` | Detects drift between Redis and DB; `--fix` to correct |

**Key design:** `EVALSHA` instead of `EVAL` — sends 40-char SHA on every hot-path call instead of full script body.

---

## Idempotency

| Change | Detail |
|---|---|
| Atomic claim | `SET NX EX` in one command — no TOCTOU race |
| User-scoped keys | `idempotency:{user_id}:{key}` — cross-user replay impossible |
| Lifecycle | `pending` → `order_id` → (TTL expiry) |
| Cached response | Duplicate of success returns same `accepted` + `order_id` |
| In-flight duplicate | Returns `processing` status |
| Min key length | `min_length=16` in Pydantic schema |

---

## Queue

| File | Purpose |
|---|---|
| `shared/stream_schema.py` | `OrderEvent` dataclass — `to_dict()` / `from_dict()` |
| `api/redis_ops.py::setup_stream` | `XGROUP CREATE ... MKSTREAM` — idempotent |
| `api/redis_ops.py::enqueue_order` | `XADD MAXLEN ~ 1_000_000` |

**Stream message fields:** `order_id`, `user_id`, `product_id`, `timestamp`, `version`

**Config added:**
```
orders_consumer_group   = "order-workers"
stream_max_len          = 1_000_000
worker_consumer_name    = "worker-1"   # override per pod
stream_claim_min_idle_ms = 30_000
```

---

## Resilience

| File | Detail |
|---|---|
| `infrastructure/redis/redis.conf` | AOF `everysec`, RDB backup, `volatile-lru` eviction |
| `infrastructure/docker-compose.redis.yml` | Primary + replica, both with AOF |
| `infrastructure/scripts/test_restart_recovery.py` | Writes 3 data types → restarts container → verifies all survive |

**AOF settings:** `appendonly yes`, `appendfsync everysec`, `aof-use-rdb-preamble yes`

---

## Test Results

```
test_no_oversell.py     500 concurrent → 100 success, 400 sold-out, final=0  PASS
test_restart_recovery.py stock + idempotency + stream → restart → all intact  PASS
```
