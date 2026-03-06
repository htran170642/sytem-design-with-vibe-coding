# Phase 6 Complete — Observability

## Files Created / Modified

| File | Purpose |
|---|---|
| `shared/metrics.py` | Central Prometheus registry (all counters, histograms, gauges) |
| `api/routes/metrics.py` | `GET /metrics` endpoint — Prometheus scrape target |
| `api/routes/buy.py` | Increments `REQUEST_COUNT` + `STOCK_REMAINING` on every outcome |
| `worker/db.py` | Records `ORDERS_PROCESSED` + `DB_WRITE_LATENCY` per insert |
| `worker/main.py` | Records `ORDERS_PROCESSED{result=failed}` on DLQ send; binds `order_id`/`msg_id` to log context |
| `shared/logging.py` | Dual logging pipeline: structlog (API) + stdlib via ProcessorFormatter (worker) |

---

## Prometheus Metrics

| Metric | Type | Labels | Where incremented |
|---|---|---|---|
| `flash_sale_requests_total` | Counter | `status` | `POST /buy` — every outcome |
| `flash_sale_stock_remaining` | Gauge | `product_id` | `POST /buy` — on accepted order |
| `flash_sale_orders_processed_total` | Counter | `result` | `worker/db.py` insert + `worker/main.py` DLQ |
| `flash_sale_db_write_seconds` | Histogram | — | `worker/db.py` — every INSERT |
| `flash_sale_queue_lag_messages` | Gauge | — | Available for worker to set periodically |

### Status / Result Labels

| Metric | Labels |
|---|---|
| `flash_sale_requests_total` | `accepted`, `sold_out`, `duplicate`, `error` |
| `flash_sale_orders_processed_total` | `inserted`, `duplicate`, `failed` |

Scrape endpoint: `GET /metrics` (Prometheus text format).

---

## Correlation IDs in Logs

Every log line now includes a correlation ID automatically via `structlog.contextvars`:

### API (structlog)
```
RequestIDMiddleware
  → bind_contextvars(request_id="req-abc")
  → all logs in that request: {"event": "...", "request_id": "req-abc", ...}
```

### Worker (stdlib logging → ProcessorFormatter)
```
Worker._process()
  → bind_contextvars(order_id="ord-123", msg_id="1234-0")
  → all logs during message processing: {"event": "...", "order_id": "ord-123", "msg_id": "1234-0", ...}
```

### Sample log lines

```json
{"event": "order_accepted", "request_id": "req-abc", "level": "info", "timestamp": "..."}
{"event": "order_inserted", "order_id": "ord-123", "msg_id": "1234-0", "level": "info", "logger": "worker.db", "timestamp": "..."}
{"event": "processing_failed_sending_to_dlq", "order_id": "ord-123", "msg_id": "1234-0", "level": "error", "logger": "worker.main.process", "timestamp": "..."}
```

---

## Logging Architecture

```
API (structlog.get_logger)
    → structlog processor chain
    → merge_contextvars (injects request_id)
    → JSONRenderer → PrintLogger → stdout

Worker (logging.getLogger)
    → stdlib root handler
    → ProcessorFormatter
    → merge_contextvars (injects order_id, msg_id)
    → JSONRenderer → StreamHandler → stdout
```

Both pipelines emit identical JSON format.
