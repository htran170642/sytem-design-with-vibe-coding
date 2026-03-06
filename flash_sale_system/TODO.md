# 🚀 High-Concurrency Flash Sale System

A distributed flash sale system designed to handle burst traffic with:
- Atomic stock control
- Idempotent order processing
- Queue-based eventual consistency
- Horizontal scalability

------------------------------------------------------------------------

# 📌 Phase 0 --- Requirements & Design

## Functional Requirements

-   [x] Users can purchase a product during flash sale
-   [x] Each user can purchase only once
-   [x] Stock must never go below zero
-   [x] Orders are processed asynchronously

## Non-Functional Requirements

-   [x] Handle 100k concurrent requests
-   [x] API latency < 50ms (P99 target)
-   [x] No overselling
-   [x] Eventual consistency acceptable
-   [x] Horizontally scalable API layer
-   [x] System survives worker crashes

## Documentation

-   [x] Create architecture diagram
-   [x] Write system design overview (README)
-   [x] Document tradeoffs and assumptions

------------------------------------------------------------------------

# 🏗 Phase 1 --- Project Setup

## Repository Structure

    flash-sale/
    ├── api/
    ├── worker/
    ├── shared/
    ├── infrastructure/
    ├── tests/
    ├── docker-compose.yml
    └── TODO.md

## Tooling

-   [x] Setup Poetry or pip-tools
-   [x] Enable strict mypy
-   [x] Setup Ruff / Flake8
-   [x] Configure pre-commit hooks
-   [x] Setup GitHub Actions CI
-   [x] Add .env configuration management

------------------------------------------------------------------------

# 🚀 Phase 2 --- API Service (FastAPI)

## Core Setup

-   [x] Initialize FastAPI app
-   [x] Add async Redis connection pool
-   [x] Add structured JSON logging
-   [x] Add request ID middleware
-   [x] Add health check endpoint

## Flash Sale Endpoint

-   [x] Implement `POST /buy`
-   [x] Validate request via Pydantic
-   [x] Require idempotency key
-   [x] Implement idempotency check in Redis
-   [x] Execute atomic stock Lua script
-   [x] Push accepted order to Redis Stream
-   [x] Return appropriate response:
    -   Success
    -   Out of stock
    -   Duplicate request

## Protection

-   [x] Implement per-user rate limiter (token bucket)
-   [x] Implement global rate limiter
-   [x] Add simple circuit breaker
-   [x] Prevent multiple purchases per user

------------------------------------------------------------------------

# ⚡ Phase 3 --- Redis Layer

## Stock Management

-   [x] Preload stock into Redis
-   [x] Implement atomic Lua decrement script
-   [x] Ensure no oversell
-   [x] Add stock reconciliation logic

## Idempotency

-   [x] Store idempotency keys with TTL
-   [x] Return cached response if duplicate request
-   [x] Protect against replay attacks

## Queue

-   [x] Setup Redis Streams
-   [x] Define stream schema
-   [x] Configure consumer group

## Resilience

-   [x] Enable AOF persistence
-   [x] Enable replication (docker setup)
-   [x] Test Redis restart recovery

## Optional Advanced:
-   [ ] Implement stock sharding
-   [ ] Implement hot-key mitigation

------------------------------------------------------------------------

# 🧵 Phase 4 --- Worker Service

## Core Worker

-   [x] Consume from Redis Stream
-   [x] Deserialize order event
-   [x] Insert order into PostgreSQL
-   [x] Acknowledge message after success
-   [x] Implement retry with exponential backoff
-   [x] Implement dead-letter queue
-   [x] Handle graceful shutdown

## Idempotent Processing

-   [x] Add UNIQUE(user_id, product_id) constraint
-   [x] Handle duplicate insert errors safely
-   [x] Ensure at-least-once safety

------------------------------------------------------------------------

# 🗄 Phase 5 --- PostgreSQL Design

## Schema

-   [x] Create `orders` table
-   [x] Add indexes:
    -   product_id
    -   user_id
    -   created_at
-   [x] Add order_status enum
-   [x] Add created_at timestamp
-   [x] Create migration scripts

## Optimization

-   [x] Benchmark insert throughput
-   [x] Add connection pooling
-   [ ] Optional: Partition by time or product

------------------------------------------------------------------------

# 📊 Phase 6 --- Observability

-   [x] Integrate Prometheus metrics
-   [x] Expose metrics:
    -   request_count
    -   success_count
    -   failure_count
    -   stock_remaining
    -   queue_lag
    -   DB_write_latency
-   [x] Add correlation IDs in logs
-   [ ] Optional: Add Grafana dashboard

------------------------------------------------------------------------

# 🔥 Phase 7 --- Load Testing

-   [x] Setup Locust
-   [x] Simulate 10k concurrent users
-   [x] Verify:
    -   No overselling
    -   Correct success count
    -   Acceptable latency
-   [x] Test retry storm scenario
-   [x] Test burst traffic scenario

------------------------------------------------------------------------

# 🧠 Phase 8 --- Failure Injection

-   [x] Kill worker during processing
-   [x] Restart Redis during event
-   [x] Simulate DB slowdown
-   [x] Validate system recovers gracefully
-   [x] Ensure no data loss

------------------------------------------------------------------------

# 🔐 Phase 9 --- Security

-   [ ] Add JWT authentication
-   [ ] Validate user identity
-   [ ] Add per-IP throttling
-   [ ] Add bot detection placeholder
-   [ ] Protect idempotency keys

------------------------------------------------------------------------

# ⚙️ Phase 10 --- Infrastructure

-   [x] Dockerize API service
-   [x] Dockerize Worker service
-   [x] Setup docker-compose:
    -   API
    -   Worker
    -   Redis
    -   PostgreSQL
-   [x] Add Makefile for local development
-   [x] Add production configuration profiles

Optional Advanced:
- [ ] Add Kubernetes manifests
- [ ] Add horizontal autoscaling config

------------------------------------------------------------------------

# 🧪 Phase 11 --- Testing

## Unit Tests

-   [x] Test Lua script logic
-   [x] Test rate limiter
-   [x] Test idempotency logic
-   [x] Test order validation

## Integration Tests

-   [x] API + Redis integration
-   [x] Worker + DB integration
-   [x] End-to-end flash sale simulation
-   [x] Add coverage reporting

------------------------------------------------------------------------

# 📐 Phase 12 --- Advanced Enhancements (Optional)

-   [ ] Implement stock sharding
-   [ ] Implement early rejection strategy
-   [ ] Add probabilistic load shedding
-   [ ] Add priority queue for VIP users
-   [ ] Add distributed tracing
-   [ ] Add multi-region simulation

------------------------------------------------------------------------

# 🏁 Final Interview Readiness Checklist

-   [x] Can explain why DB locking is bad under high concurrency
-   [x] Can explain atomic Lua script guarantees
-   [x] Can explain idempotency strategy
-   [x] Can explain eventual consistency tradeoff
-   [x] Can explain hot-key problem
-   [x] Can explain scaling Redis
-   [x] Can explain failure recovery scenarios
-   [x] Can explain backpressure handling

------------------------------------------------------------------------

# 🎯 Stretch Goals (Elite Level)

-   [ ] Implement Redis cluster mode
-   [ ] Simulate exactly-once processing
-   [ ] Build minimal custom message queue
-   [ ] Achieve 50k+ RPS in load test
-   [ ] Document benchmarking results
