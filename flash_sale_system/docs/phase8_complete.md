# Phase 8 Complete — Failure Injection

## Files Created

| File | Failure Simulated |
|---|---|
| `infrastructure/scripts/test_worker_crash.py` | Worker crash before XACK |
| `infrastructure/scripts/test_redis_restart.py` | Redis container restart |
| `infrastructure/scripts/test_db_slowdown.py` | PostgreSQL slowdown / connection exhaustion |

---

## Test 1 — Worker Crash (Kill before XACK)

**Mechanism:** Worker reads 5 messages into PEL but crashes (never calls XACK).
Recovery worker uses `XAUTOCLAIM` to reclaim stale messages and reprocess them.

| Check | Result |
|---|---|
| Messages in PEL after crash | 5 (all preserved) |
| DB rows before recovery | 0 |
| DB rows after recovery | 5 |
| Duplicates | 0 (`ON CONFLICT DO NOTHING`) |
| PEL after recovery | 0 (cleared) |

**Why it works:** Redis never removes a PEL entry until `XACK` is called.
On worker restart, `XAUTOCLAIM` reclaims any message idle > `stream_claim_min_idle_ms`.

---

## Test 2 — Redis Restart (AOF Persistence)

**Mechanism:** Write stock + stream data → `docker restart flash_redis` → verify all data survived.
Redis container has `appendonly yes` + `appendfsync everysec` mounted from `infrastructure/redis/redis.conf`.

| Data | Before | After | Preserved |
|---|---|---|---|
| `stock:PROD-RESTART-TEST` | 50 | 50 | ✓ |
| Stream messages | 5 | 5 | ✓ |
| PEL entries | 5 | 5 | ✓ |
| Redis restart time | — | 0.5s | ✓ |

**Why it works:** AOF logs every write command to disk (`appendonly.aof`).
On restart, Redis replays the AOF file to reconstruct exact in-memory state.

---

## Test 3 — DB Slowdown (Retry + Backoff)

**Mechanism:** First attempt per message raises `TooManyConnectionsError` after 0.8s delay
(simulates connection pool exhaustion / lock wait). Second attempt succeeds normally.

| Check | Result |
|---|---|
| Orders permanently failed | 0 |
| Orders that hit slow path | 3 / 3 |
| Orders landed in DB | 3 |
| PEL after processing | 0 |
| Avg latency (with retry) | ~1.0s |

**Why it works:** `with_retry()` catches transient errors and backs off exponentially.
XACK is only called **after** successful insert — slow messages stay in PEL and are retried.

---

## Key Guarantees Validated

| Guarantee | Test | Mechanism |
|---|---|---|
| No data loss on worker crash | Test 1 | PEL + XAUTOCLAIM |
| No data loss on Redis restart | Test 2 | AOF `appendfsync everysec` |
| No data loss on DB slowdown | Test 3 | `with_retry` + backoff |
| No duplicate orders | All tests | `ON CONFLICT DO NOTHING` |
| Messages only XACK'd after success | All tests | XACK after insert, not before |
