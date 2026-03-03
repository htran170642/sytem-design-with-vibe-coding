"""
Metrics Service
Prometheus metrics definitions for AIVA application
Phase 10: Observability & Monitoring - Step 4
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP Request Metrics
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "aiva_http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "aiva_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

active_http_requests = Gauge(
    "aiva_active_http_requests",
    "Number of currently active HTTP requests",
)

http_errors_total = Counter(
    "aiva_http_errors_total",
    "Total number of HTTP error responses (4xx/5xx)",
    ["method", "path", "status_code"],
)

# ---------------------------------------------------------------------------
# LLM / AI Request Metrics
# ---------------------------------------------------------------------------

llm_requests_total = Counter(
    "aiva_llm_requests_total",
    "Total number of LLM API requests",
    ["model", "status"],  # status: success | error | timeout
)

llm_request_duration_seconds = Histogram(
    "aiva_llm_request_duration_seconds",
    "LLM API request duration in seconds",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

llm_tokens_total = Counter(
    "aiva_llm_tokens_total",
    "Total number of LLM tokens used",
    ["model", "token_type"],  # token_type: prompt | completion
)

llm_cost_dollars_total = Counter(
    "aiva_llm_cost_dollars_total",
    "Cumulative LLM API cost in USD",
    ["model"],
)

# ---------------------------------------------------------------------------
# Cache Metrics
# ---------------------------------------------------------------------------

cache_operations_total = Counter(
    "aiva_cache_operations_total",
    "Total cache operations",
    ["operation", "result"],  # operation: get | set; result: hit | miss | error
)

# ---------------------------------------------------------------------------
# Document Processing Metrics
# ---------------------------------------------------------------------------

documents_processed_total = Counter(
    "aiva_documents_processed_total",
    "Total number of documents processed",
    ["status"],  # status: success | error
)
