"""
Prometheus metrics registry for the flash-sale system.

All counters/histograms are defined here so both the API and worker
can import them from a single place without double-registration.
"""

from prometheus_client import REGISTRY, Counter, Gauge, Histogram  # noqa: F401

# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "flash_sale_requests_total",
    "Total POST /buy requests received",
    ["status"],  # labels: accepted | sold_out | duplicate | error
)

# ---------------------------------------------------------------------------
# Stock metric
# ---------------------------------------------------------------------------

STOCK_REMAINING = Gauge(
    "flash_sale_stock_remaining",
    "Current stock level in Redis",
    ["product_id"],
)

# ---------------------------------------------------------------------------
# Worker metrics
# ---------------------------------------------------------------------------

ORDERS_PROCESSED = Counter(
    "flash_sale_orders_processed_total",
    "Orders written to PostgreSQL by the worker",
    ["result"],  # labels: inserted | duplicate | failed
)

DB_WRITE_LATENCY = Histogram(
    "flash_sale_db_write_seconds",
    "PostgreSQL INSERT latency in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

QUEUE_LAG = Gauge(
    "flash_sale_queue_lag_messages",
    "Approximate number of unprocessed messages in the orders stream",
)
