# TODO — Real-Time Fraud Detection System (FraudSense)

Goal: Build an interview-ready **real-time fraud detection backend** that:
- Ingests transaction events via REST
- Publishes them to a broker (Kafka/RabbitMQ)
- Processes them in background workers (Celery/Ray)
- Scores fraud risk via ML (Isolation Forest + rules)
- Stores all in PostgreSQL
- Pushes high-risk alerts in **real time via WebSocket**
- Scales horizontally on **AKS** with proper **observability** and **CI/CD**

Use this as a **step-by-step checklist** you can literally follow and show in interviews.

---

## Phase 0 — Repo Setup & Architecture

### 0.1 Create repo & base layout

- [ ] Create repo: `fraudsense`  
- [ ] Create directories:
  - [ ] `/api` — FastAPI service
  - [ ] `/worker` — Celery/Ray worker service
  - [ ] `/infra` — Docker, k8s, compose, scripts
  - [ ] `/docs` — architecture diagrams, notes, demo script
- [ ] Add root files:
  - [ ] `README.md` — short project intro
  - [ ] `TODO.md` — this file
  - [ ] `.gitignore` — Python, venv, __pycache__, etc.

### 0.2 Architecture design

- [ ] Draw rough diagram (`/docs/architecture.drawio` or `.md`):
  - Client → FastAPI `/transactions`
  - FastAPI → Broker topic/queue `transactions`
  - Worker → consumes, scores, updates Postgres, generates alerts
  - WebSocket `/alerts/stream` → browser dashboard
- [ ] Document main **components** in `/docs/architecture.md`:
  - [ ] API service
  - [ ] Worker service
  - [ ] PostgreSQL
  - [ ] Redis
  - [ ] Broker (Kafka or RabbitMQ)
  - [ ] Metrics (Prometheus/Grafana)
  - [ ] AKS + ACR

---

## Phase 1 — FastAPI API + PostgreSQL (Local)

### 1.1 FastAPI app skeleton

Inside `/api`:

- [ ] Create `pyproject.toml` or `requirements.txt` with:
  - `fastapi`
  - `uvicorn[standard]`
  - `pydantic`
  - `SQLAlchemy` or `SQLModel`
  - `asyncpg` (if async)
  - `python-dotenv`
- [ ] Create structure:
  - [ ] `api/app/main.py`
  - [ ] `api/app/config.py`
  - [ ] `api/app/models.py`
  - [ ] `api/app/schemas.py`
  - [ ] `api/app/db.py`
  - [ ] `api/app/routers/transactions.py`
- [ ] Implement `main.py`:
  - [ ] Create `FastAPI()` app
  - [ ] Include router for `/transactions`
  - [ ] Add `/health` endpoint

### 1.2 Database setup (local Postgres)

In `/infra/docker-compose.yml`:

- [ ] Add Postgres service:
  - Image: `postgres:16`
  - Env: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=fraudsense`
  - Volume: `pgdata:/var/lib/postgresql/data`
- [ ] Expose port `5432` for local dev

In `/api/app/db.py`:

- [ ] Create SQLAlchemy engine (or async engine)
- [ ] Create session factory (or async session)
- [ ] Configurable via env vars: DB host, port, user, password, database

### 1.3 Define DB models & Pydantic schemas

In `/api/app/models.py` (SQLAlchemy):

- [ ] Define `Transaction` model with fields:
  - `id` (PK, UUID or bigint)
  - `transaction_id` (unique string)
  - `account_id` (string)
  - `amount` (numeric)
  - `currency` (string)
  - `timestamp` (timestamptz)
  - `merchant_id` (string)
  - `geo_lat`, `geo_lon` (numeric)
  - `raw_payload` (JSONB)
  - `created_at` (timestamptz, default now)
- [ ] Define `Score` model:
  - `id` (PK)
  - `transaction_id` (FK)
  - `model_version` (string)
  - `score` (float)
  - `risk_label` (enum or string)
  - `created_at`
- [ ] Define `Alert` model:
  - `id` (PK)
  - `transaction_id` (FK)
  - `account_id`
  - `reason` (text/json)
  - `threshold`
  - `created_at`
  - `acknowledged_at` (nullable)

In `/api/app/schemas.py`:

- [ ] Define Pydantic models:
  - `TransactionIn` — input from client
  - `TransactionOut` — transaction + score
  - `AlertOut` — alert payload for API/WS

### 1.4 Implement core endpoints (without broker yet)

In `/api/app/routers/transactions.py`:

- [ ] Implement `POST /transactions`:
  - [ ] Parse `TransactionIn`
  - [ ] Insert row into `transactions` table
  - [ ] Return `202 Accepted` with `{ "transaction_id": ..., "status": "queued" }` (for now just stored)
- [ ] Implement `GET /transactions/{transaction_id}`:
  - [ ] Query `transactions` + optional join with `scores`
  - [ ] Return `TransactionOut`

### 1.5 Basic tests

Create `/api/tests/test_transactions.py`:

- [ ] Test `POST /transactions` with valid payload → `202`
- [ ] Test `GET /transactions/{id}` returns stored data
- [ ] Add `pytest` config and `conftest.py` for test DB

---

## Phase 2 — Broker + Worker (Event-Driven Core)

### 2.1 Add message broker via docker-compose

In `/infra/docker-compose.yml`:

Choose **Kafka** or **RabbitMQ** (pick one and stick to it). Example: RabbitMQ

- [ ] Add RabbitMQ service:
  - Image: `rabbitmq:3-management`
  - Ports: `5672` (AMQP), `15672` (management UI)
  - Env: default user/pwd

### 2.2 Publish messages in API on transaction creation

In `/api/app/services/producer.py`:

- [ ] Create function `publish_transaction_created(transaction_id: str)`:
  - [ ] Connect to broker (e.g., `pika` for RabbitMQ)
  - [ ] Publish JSON: `{ "transaction_id": "...", "event": "transaction.created" }` to queue `transactions`

Update `POST /transactions`:

- [ ] After inserting DB row, call `publish_transaction_created(transaction_id)`

### 2.3 Worker project scaffolding

In `/worker`:

- [ ] Create `pyproject.toml` / `requirements.txt`:
  - `celery`
  - `pika` or Kafka client
  - `SQLAlchemy` / `asyncpg`
  - `redis`
  - `joblib`
  - `scikit-learn`
- [ ] Create files:
  - [ ] `worker/app/celery_app.py`
  - [ ] `worker/app/tasks.py`
  - [ ] `worker/app/db.py`
  - [ ] `worker/app/config.py`
  - [ ] `worker/app/model_loader.py`

### 2.4 Celery setup

In `worker/app/celery_app.py`:

- [ ] Define Celery app:
  - Broker URL = RabbitMQ
  - Backend = Redis or DB
- [ ] Autodiscover tasks from `worker.app.tasks`

In `worker/app/tasks.py`:

- [ ] Implement `@celery_app.task` `process_transaction(transaction_id: str)`:
  - [ ] Load transaction from Postgres (using `db.py`)
  - [ ] (For now) compute dummy score, e.g., `amount > threshold -> HIGH`
  - [ ] Insert score row into `scores`
  - [ ] Insert alert row into `alerts` if `HIGH`

### 2.5 Connect broker queue to Celery workers

- [ ] Decide integration pattern:
  - Option A: API publishes directly to Celery via `.delay()` (simpler)
  - Option B: API publishes to broker queue, separate consumer pushes to Celery (more realistic, but complex)
- [ ] For MVP, use **Option A**:
  - [ ] Add small Celery client in API, call `process_transaction.delay(transaction_id)` after DB insert

### 2.6 Integration tests

In `/api/tests/test_integration_processing.py`:

- [ ] Spin up services via docker-compose (or test env)
- [ ] `POST /transactions`
- [ ] Poll DB until `scores` has entry for that `transaction_id`
- [ ] Assert score exists and is linked

---

## Phase 3 — ML Model (Isolation Forest) + Real Scoring

### 3.1 Training script

In `/worker/model/train_isolation_forest.py`:

- [ ] Generate synthetic dataset:
  - Features: amount, hour_of_day, num_tx_last_5min, geo_distance, merchant_risk_score, etc.
  - Label: normal vs anomalous
- [ ] Train `IsolationForest`:
  - [ ] Fit on mostly normal traffic
  - [ ] Save model using `joblib.dump(model, "model/isolation_forest_v1.joblib")`
- [ ] Commit generated model file or script to recreate it

### 3.2 Model loader

In `worker/app/model_loader.py`:

- [ ] On module import or function call, load model from `model/` dir
- [ ] Lazy-load and cache instance to avoid reloading for each task
- [ ] Provide `get_model()` function

### 3.3 Feature extraction

In `worker/app/features.py`:

- [ ] Implement `extract_features(transaction, redis_client) -> np.array`:
  - [ ] Use transaction fields: `amount`, `currency`, `timestamp`, `geo`, `merchant_id`
  - [ ] Use Redis to fetch:
    - Count of transactions for same account in last X minutes
    - Last transaction location → compute distance
    - Average amount for this account
- [ ] Ensure consistent feature order

### 3.4 Integrate model into worker task

Update `process_transaction` task:

- [ ] Load transaction from DB
- [ ] Call `extract_features(...)`
- [ ] Call `model.decision_function(features)` or `.score_samples(features)`
- [ ] Map raw score to risk label:
  - Example:
    - score < -0.3 → HIGH
    - -0.3 ≤ score < -0.1 → MEDIUM
    - otherwise → LOW
- [ ] Store into `scores` table with:
  - `score`, `risk_label`, `model_version="iforest_v1"`
- [ ] If `HIGH`, create `alert` with reason string (e.g., "isolation_forest_high_score")

### 3.5 Unit tests

- [ ] Test `extract_features` with known transaction + redis state
- [ ] Test risk label mapping given score thresholds
- [ ] Test `process_transaction` with a test transaction and mock model

---

## Phase 4 — Redis: Rate Limiting & Sliding Window

### 4.1 Redis setup

In `docker-compose.yml`:

- [ ] Add Redis service:
  - Image: `redis:7`
  - Port: `6379`

In both API and worker:

- [ ] Create `redis_client` helper (host, port from env)
- [ ] Wrap in reusable module `app/redis_client.py`

### 4.2 Rate limiting in API

In `POST /transactions`:

- [ ] Before inserting:
  - [ ] Increment a key `rate:account:{account_id}:{minute_bucket}`
  - [ ] If count exceeds threshold (e.g. 60/min), return `429 Too Many Requests` or tag for alert

### 4.3 Sliding window counts for features

In worker’s `extract_features`:

- [ ] Maintain per-account transaction timestamps in Redis (e.g., sorted set)
- [ ] On each transaction:
  - [ ] Add timestamp to sorted set `tx:account:{account_id}`
  - [ ] Remove entries older than 1h (ZREMRANGEBYSCORE)
  - [ ] Count elements to get `num_tx_last_1h` feature

- [ ] Add unit tests for sliding-window logic

---

## Phase 5 — WebSocket Alerts & Simple Dashboard

### 5.1 WebSocket endpoint

In `/api/app/routers/alerts.py`:

- [ ] Implement `WS /alerts/stream`:
  - [ ] On connect, register client connection
  - [ ] Listen to a Redis pub/sub channel `alerts`
  - [ ] When message received (new alert), forward JSON to all connected clients

### 5.2 Worker → alert broadcast

In worker `process_transaction` when alert created:

- [ ] Publish alert payload to Redis pub/sub channel `alerts`
  - Payload example:
  ```json
  {
    "alert_id": "...",
    "transaction_id": "...",
    "account_id": "...",
    "risk_label": "HIGH",
    "created_at": "...",
    "reason": "iforest_high_score"
  }
  ```

### 5.3 Frontend / mini dashboard

Create `/api/static/dashboard.html` (or separate frontend):

- [ ] Minimal HTML + JS:
  - [ ] JS opens WebSocket to `/alerts/stream`
  - [ ] On message, parse JSON and append row to alerts table
- [ ] Include columns: time, account_id, amount (if provided), risk_label, reason

### 5.4 Manual verification

- [ ] Start full stack with docker-compose
- [ ] Open dashboard in browser
- [ ] Send synthetic HIGH-risk transaction via curl/Postman
- [ ] Confirm alert appears in real-time on dashboard

---

## Phase 6 — Observability: Metrics, Logs, Traces

### 6.1 Logging

- [ ] Configure structured logs (JSON) using `structlog` or `logging` + formatter
- [ ] Include fields: `trace_id`, `transaction_id`, `account_id`, `component` (api/worker)

### 6.2 Prometheus metrics

In API and worker:

- [ ] Add `prometheus_client`:
  - Counters:
    - `transactions_ingested_total`
    - `transactions_processed_total`
    - `alerts_created_total`
  - Histograms:
    - `transaction_processing_seconds`
- [ ] Expose `/metrics` endpoint in API & worker

In `docker-compose`:

- [ ] Add Prometheus and Grafana services
- [ ] Configure Prometheus to scrape API/worker `/metrics`

### 6.3 Dashboards

In Grafana:

- [ ] Create dashboard panels for:
  - Transactions per second
  - Alerts per minute
  - Avg processing latency
  - Worker success vs failure counts

### 6.4 (Stretch) Tracing

- [ ] Integrate OpenTelemetry in FastAPI and Celery
- [ ] Export traces to Jaeger/Tempo
- [ ] Ensure a single `trace_id` follows a transaction from API → worker → DB

---

## Phase 7 — Dockerization & Local Orchestration

### 7.1 Dockerfiles

In `/api/Dockerfile`:

- [ ] Use Python 3.11 base
- [ ] Copy app, install deps
- [ ] Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

In `/worker/Dockerfile`:

- [ ] Use Python 3.11 base
- [ ] Copy worker code and model
- [ ] Command: `celery -A worker.app.celery_app worker --loglevel=info`

### 7.2 docker-compose for full local stack

In `/infra/docker-compose.yml`:

Services:
- [ ] `api` — build from `/api`
- [ ] `worker` — build from `/worker`
- [ ] `postgres`
- [ ] `redis`
- [ ] `rabbitmq` (or kafka)
- [ ] `prometheus`
- [ ] `grafana`

Add named volumes where needed, networks for isolation.

### 7.3 Convenience scripts

- [ ] Create `Makefile` (or scripts) with commands:
  - `make up` — `docker-compose up -d`
  - `make down` — `docker-compose down -v`
  - `make logs` — tails logs
  - `make test` — runs pytest in api + worker

---

## Phase 8 — Azure & AKS Deployment

### 8.1 Azure Container Registry (ACR)

- [ ] Create ACR instance
- [ ] Configure local Docker to login to ACR
- [ ] Tag and push images:
  - `fraudsense/api:tag`
  - `fraudsense/worker:tag`

### 8.2 AKS cluster

- [ ] Create AKS cluster (via CLI or portal)
- [ ] Connect kubectl context to cluster

### 8.3 Kubernetes manifests / Helm

In `/infra/k8s/`:

- [ ] `deployment-api.yaml`
- [ ] `service-api.yaml`
- [ ] `deployment-worker.yaml`
- [ ] `service-worker-metrics.yaml` (for Prom scrape)
- [ ] ConfigMaps/Secrets for:
  - DB connection
  - Redis connection
  - Broker URL
  - Model path / envs
- [ ] Optionally Ingress for API

### 8.4 Deploy and verify

- [ ] `kubectl apply -f infra/k8s/`
- [ ] Port-forward or use Ingress to test:
  - `POST /transactions`
  - Worker processes messages
  - DB entries created
  - Alerts generated and streamable

---

## Phase 9 — Autoscaling & Load Testing

### 9.1 Horizontal Pod Autoscaler (HPA)

- [ ] Create `hpa-worker.yaml`:
  - Target worker deployment
  - Min/max replicas (e.g., 2–20)
  - Scale on CPU usage initially

### 9.2 (Stretch) KEDA or custom metrics

- [ ] Install KEDA in AKS
- [ ] Configure scaled object based on:
  - RabbitMQ queue length **or**
  - Kafka consumer lag
- [ ] Tie worker deployment to queue metric

### 9.3 Load tests (locust / k6)

- [ ] Write load script:
  - Constant arrival rate of transactions
  - Simulate multiple accounts/merchants
- [ ] Run against AKS API endpoint
- [ ] Observe:
  - QPS
  - p95 latency
  - Worker replicas scaling up/down
- [ ] Capture screenshots for `/docs`

---

## Phase 10 — Testing, CI/CD, and Final Polish

### 10.1 Testing coverage

- [ ] API tests:
  - Validation, error handlers
  - DB interactions (happy path + failure)
- [ ] Worker tests:
  - Feature extraction
  - Model scoring
  - Alert generation
- [ ] End-to-end test:
  - Given synthetic suspicious transactions → assert alerts in DB

### 10.2 GitHub Actions CI

In `.github/workflows/ci.yml`:

- [ ] Steps:
  - Checkout
  - Setup Python
  - Install api + worker deps
  - Run `ruff` / `black --check`
  - Run `pytest`
  - Build Docker images
  - (On main branch) Push to ACR

### 10.3 Optional CD (deploy on tag)

In `.github/workflows/cd.yml`:

- [ ] Trigger on tag release (e.g., `v*`)
- [ ] Login to Azure (service principal)
- [ ] Pull images from ACR
- [ ] `kubectl apply -f infra/k8s`
- [ ] Run smoke test (curl `GET /health`)

### 10.4 Docs & demo

- [ ] Update `README.md` with:
  - Project summary
  - Architecture diagram
  - How to run locally
  - How to deploy to AKS
- [ ] Create `/docs/demo-script.md` with:
  - Step-by-step demo for interview (3–7 minutes)
- [ ] (Nice) Record short screen capture showing:
  - Posting transactions
  - Alerts appearing on dashboard
  - Metrics dashboard

---

## Stretch Improvements (Do if you have time)

- [ ] Postgres partitioning or TimescaleDB integration for large volumes
- [ ] Model versioning and routing (canary model deployments)
- [ ] Simple analyst UI to acknowledge/close alerts
- [ ] Security hardening:
  - JWT auth for API
  - Role-based access for dashboard
  - Network policies in AKS
- [ ] Chaos tests:
  - Kill worker pods
  - Stop broker
  - See how system recovers and what breaks
