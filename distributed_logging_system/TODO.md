# 📝 Implementation Roadmap

## Phase 0 — Project Setup ✅

- [x] Create Git repository `observability-platform-poc`
- [x] Initialize Python 3.11 project
- [x] Setup `pyproject.toml` with dependencies
- [x] Create base folder structure
- [x] Setup pre-commit hooks (black, isort, ruff)
- [x] Add Makefile with common commands
- [x] Create .env.example
- [x] Create .gitignore
- [x] Create README.md

## Phase 1 — Data Collection (Agents) 🚧

### Logs Agent
- [ ] Implement `LogAgent` in Python
- [ ] Tail files or stdout
- [ ] Batch logs
- [ ] Attach metadata (service, env, host, timestamp)
- [ ] Send to ingestion API

### Metrics Agent
- [ ] Collect CPU, memory, disk using `psutil`
- [ ] Emit metrics every N seconds
- [ ] Send metrics to ingestion API
- [ ] Add local buffering (disk or memory queue)
- [ ] Add retry with exponential backoff

## Phase 2 — Ingestion Service (FastAPI) ⏳

- [ ] Create FastAPI service `ingestion_service`
- [ ] Endpoints: `POST /logs`, `POST /metrics`, `POST /events`
- [ ] Validate schema (Pydantic)
- [ ] Add rate limiting
- [ ] Add authentication (simple API key)
- [ ] Write events to Kafka (or Redpanda)

## Phase 3 — Message Bus ⏳

- [ ] Setup Kafka or Redpanda in Docker Compose
- [ ] Create topics: `logs.raw`, `metrics.raw`, `events.raw`
- [ ] Configure partitions + replication
- [ ] Add retention policies

## Phase 4 — Stream Processing ⏳

- [ ] Implement `LogProcessor`
  - [ ] Parse raw logs
  - [ ] Extract labels
  - [ ] Normalize format
- [ ] Implement `MetricsProcessor`
  - [ ] Aggregate per service
  - [ ] Compute rolling averages, p95
- [ ] Implement anomaly detector (simple z-score / rules)
- [ ] Consumers subscribe to Kafka topics
- [ ] Write processed data to storage

## Phase 5 — Storage ⏳

### Hot Storage
- [ ] Setup OpenSearch / Elasticsearch
- [ ] Define index templates for logs & metrics
- [ ] Implement writers

### Warm Storage
- [ ] Setup S3 / MinIO
- [ ] Write Parquet or JSONL files periodically

### Retention
- [ ] Hot retention: 7 days
- [ ] Warm retention: 30 days
- [ ] Cold retention: archive only

## Phase 6 — Query API ⏳

- [ ] Build FastAPI `query_service`
- [ ] Endpoints: `GET /logs/search`, `GET /metrics/query`, `GET /services`
- [ ] Implement pagination + filters
- [ ] Add auth + tenant isolation

## Phase 7 — UI & Visualization ⏳

- [ ] Setup Grafana
- [ ] Connect Grafana to OpenSearch
- [ ] Build dashboards:
  - [ ] Error rate
  - [ ] Latency p95
  - [ ] Log volume per service
- [ ] Configure alert rules

## Phase 8 — Reliability & Scaling ⏳

- [ ] Add health checks to all services
- [ ] Add readiness/liveness probes
- [ ] Add circuit breaker for Kafka
- [ ] Add DLQ for bad messages
- [ ] Add load testing (Locust / k6)

## Phase 9 — Security ⏳

- [ ] Add TLS
- [ ] Mask sensitive fields
- [ ] Add RBAC for dashboards
- [ ] Implement audit logging

## Phase 10 — Observability of Observability ⏳

- [ ] Monitor ingestion latency
- [ ] Monitor Kafka lag
- [ ] Monitor storage growth
- [ ] Alert on pipeline failures

## Phase 11 — Documentation ⏳

- [ ] Architecture diagram
- [ ] Data flow diagram
- [ ] Deployment guide
- [ ] Tradeoffs & limitations doc
- [ ] Interview explanation notes

## Phase 12 — Interview Readiness ⏳

- [ ] Prepare 5-minute explanation
- [ ] Prepare scaling story
- [ ] Prepare failure scenarios
- [ ] Prepare cost discussion

## Stretch Goals ⏳

- [ ] Multi-tenant isolation
- [ ] Sampling
- [ ] Trace support (OpenTelemetry)
- [ ] Kubernetes deployment
- [ ] Auto-scaling

---

**Legend:**
- ✅ Complete
- 🚧 In Progress
- ⏳ Not Started
