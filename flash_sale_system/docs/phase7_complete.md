# Phase 7 Complete — Load Testing

## Files Created

| File | Purpose |
|---|---|
| `tests/load/locustfile.py` | Locust scenario — `FlashSaleUser` with outcome breakdown hook |
| `infrastructure/scripts/test_retry_storm.py` | 200 users × 10 retries each — worst-case retry amplification |
| `infrastructure/scripts/test_burst_traffic.py` | 1000 users at t=0 (starting gun pattern) — thundering herd |

---

## Test 1 — Locust Load Test (5000 users, 30s)

```
locust -f tests/load/locustfile.py --headless -u 5000 -r 500 --run-time 30s
```

| Metric | Result |
|---|---|
| Total requests | 43,511 |
| Failures | **0 (0%)** |
| Throughput | ~1,300 req/s |
| P50 latency | 510ms |
| P95 latency | 1,300ms |
| P99 latency | 14,000ms* |
| Units sold | exactly 1,000 (= stock) |
| Oversell | **None** |

*P99 inflated by Locust's own CPU saturation on a single machine — distribute Locust for accurate tail latency.

**Outcome breakdown:**
```
accepted   :  13,595  (real purchases + idempotency cache hits)
sold_out   :  29,916  (after stock exhausted)
```

---

## Test 2 — Retry Storm (200 users × 10 retries)

| Metric | Result |
|---|---|
| Max possible requests | 2,000 |
| Accepted | 10 (= stock) |
| `sold_out` hits absorbed | 1,900 |
| 5xx errors | **0** |
| Oversell | **None** |

Stock = 10, 190 users exhausted all retries and gave up. API stayed healthy throughout.

---

## Test 3 — Burst Traffic (1000 users at t=0)

| Metric | Result |
|---|---|
| Total requests | 1,000 (fired simultaneously) |
| Throughput | ~155 req/s |
| Accepted P50 | 1,391ms |
| Accepted P99 | 2,494ms |
| Sold-out P50 | 6,063ms |
| 5xx errors | **0** |
| Units sold | exactly 100 (= stock) |
| Oversell | **None** |

---

## Key Findings

| Property | Verified |
|---|---|
| No overselling under load | ✓ Lua atomic decrement holds under all scenarios |
| API survives retry storms | ✓ Per-user rate limiter absorbs amplification |
| API survives thundering herd | ✓ Redis handles burst; no DB on hot path |
| Zero 5xx errors across all tests | ✓ Circuit breaker + error handling stable |
