# Prometheus Alerting Rules — AIVA

Suggested alert rules for Prometheus. Save as `prometheus/alerts.yml` and
reference it from `prometheus.yml` via `rule_files`.

---

## Alert Rules

```yaml
groups:
  - name: aiva_http
    rules:
      # High error rate — more than 5 % of responses are 5xx over 5 minutes
      - alert: HighHTTPErrorRate
        expr: |
          sum(rate(aiva_http_requests_total{status_code=~"5.."}[5m]))
          /
          sum(rate(aiva_http_requests_total[5m])) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High HTTP 5xx error rate ({{ $value | humanizePercentage }})"
          description: >
            More than 5 % of HTTP responses are server errors over the last
            5 minutes.

      # High client error rate — more than 10 % of responses are 4xx
      - alert: HighHTTPClientErrorRate
        expr: |
          sum(rate(aiva_http_requests_total{status_code=~"4.."}[5m]))
          /
          sum(rate(aiva_http_requests_total[5m])) > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High HTTP 4xx error rate ({{ $value | humanizePercentage }})"
          description: >
            More than 10 % of HTTP responses are client errors over the last
            5 minutes. May indicate bad client requests or auth failures.

      # Slow P95 response time — 95th percentile latency above 2 s
      - alert: SlowHTTPResponseTime
        expr: |
          histogram_quantile(0.95,
            sum(rate(aiva_http_request_duration_seconds_bucket[5m])) by (le, path)
          ) > 2.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow HTTP P95 latency on {{ $labels.path }} ({{ $value | humanizeDuration }})"
          description: >
            The 95th-percentile request latency on path {{ $labels.path }}
            exceeds 2 seconds.

  - name: aiva_llm
    rules:
      # LLM error rate — more than 10 % of LLM calls fail
      - alert: HighLLMErrorRate
        expr: |
          sum(rate(aiva_llm_requests_total{status=~"error|timeout"}[5m]))
          /
          sum(rate(aiva_llm_requests_total[5m])) > 0.10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High LLM error/timeout rate ({{ $value | humanizePercentage }})"
          description: >
            More than 10 % of LLM API calls are failing or timing out.
            Check OpenAI API key validity and network connectivity.

      # Slow LLM P95 latency — above 15 s
      - alert: SlowLLMResponseTime
        expr: |
          histogram_quantile(0.95,
            sum(rate(aiva_llm_request_duration_seconds_bucket[10m])) by (le, model)
          ) > 15.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow LLM P95 latency for {{ $labels.model }} ({{ $value | humanizeDuration }})"
          description: >
            The 95th-percentile LLM request latency for model {{ $labels.model }}
            exceeds 15 seconds.

      # High token consumption — more than 100k tokens/min across all models
      - alert: HighTokenConsumption
        expr: |
          sum(rate(aiva_llm_tokens_total[1m])) * 60 > 100000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High LLM token consumption ({{ $value | humanize }} tokens/min)"
          description: >
            Token consumption exceeds 100,000 tokens per minute. Review
            usage or check for runaway requests.

  - name: aiva_availability
    rules:
      # No requests received — possible deployment or network issue
      - alert: NoIncomingRequests
        expr: |
          sum(rate(aiva_http_requests_total[5m])) == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "No incoming HTTP requests"
          description: >
            AIVA has received zero HTTP requests in the last 5 minutes.
            The service may be unreachable or there may be a load-balancer issue.
```

---

## Prometheus Scrape Config

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: aiva
    static_configs:
      - targets: ["aiva-api:8000"]   # adjust host/port as needed
    metrics_path: /metrics
    scrape_interval: 15s
```

---

## Grafana Dashboard Queries

| Panel | PromQL |
|-------|--------|
| Request rate (req/s) | `sum(rate(aiva_http_requests_total[1m]))` |
| Error rate (%) | `sum(rate(aiva_http_requests_total{status_code=~"5.."}[1m])) / sum(rate(aiva_http_requests_total[1m])) * 100` |
| P50 / P95 / P99 latency | `histogram_quantile(0.95, sum(rate(aiva_http_request_duration_seconds_bucket[5m])) by (le))` |
| Active requests | `aiva_active_http_requests` |
| LLM requests/min | `sum(rate(aiva_llm_requests_total[1m])) * 60` |
| LLM P95 latency | `histogram_quantile(0.95, sum(rate(aiva_llm_request_duration_seconds_bucket[5m])) by (le, model))` |
| Tokens/min | `sum(rate(aiva_llm_tokens_total[1m])) by (model, token_type) * 60` |
| Cumulative cost ($) | `sum(aiva_llm_cost_dollars_total) by (model)` |
| Cache hit rate (%) | `sum(rate(aiva_cache_operations_total{result="hit"}[5m])) / sum(rate(aiva_cache_operations_total[5m])) * 100` |
