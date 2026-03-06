# Phase 4 Complete — Worker Service

## Files Created

| File | Purpose |
|---|---|
| `worker/consumer.py` | XREADGROUP poll loop + XAUTOCLAIM crash recovery |
| `worker/db.py` | Idempotent `INSERT ... ON CONFLICT DO NOTHING` via asyncpg |
| `worker/retry.py` | Exponential backoff (base 0.5s, cap 10s, ±20% jitter) |
| `worker/dlq.py` | Dead-letter queue — XADD to `orders.dlq` + XACK original |
| `worker/main.py` | Entry point — wires all above, handles SIGTERM/SIGINT |
| `infrastructure/postgres/init.sql` | Orders table with `UNIQUE(user_id, product_id)` |
| `infrastructure/scripts/test_at_least_once.py` | Crash simulation test |

---

## Processing Pipeline

```
XAUTOCLAIM (stale PEL on startup)
        │
        ▼
XREADGROUP (new messages, block=2s)
        │
        ▼
with_retry(insert_order, max_attempts=3, backoff=0.5s..10s)
        │
        ├─ success  → XACK
        └─ exhausted → send_to_dlq → XADD orders.dlq + XACK
```

## At-Least-Once Guarantee

| Scenario | Outcome |
|---|---|
| Worker processes + ACKs | Message removed from PEL ✓ |
| Worker crashes before XACK | Message stays in PEL → reclaimed by next worker via XAUTOCLAIM ✓ |
| DB transient failure | Retried up to 3× with backoff, then DLQ ✓ |
| Duplicate redelivery | `ON CONFLICT DO NOTHING` → False return → XACK safely ✓ |

## Idempotency Layers

```
API:    SET NX EX (Redis)             — prevents duplicate stream entries
Worker: ON CONFLICT DO NOTHING (SQL)  — prevents duplicate DB rows
DB:     UNIQUE(user_id, product_id)   — ultimate source of truth
```

## Test Results

```
test_at_least_once.py
  worker-1 reads message → crashes (no XACK)
  PEL count = 1 (message stuck)
  worker-2 XAUTOCLAIM reclaims it
  DB rows = 1 (exactly-once despite redelivery)   PASS
```
