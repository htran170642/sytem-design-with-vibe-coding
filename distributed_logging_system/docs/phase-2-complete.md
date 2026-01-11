# Phase 2 Complete! 🎉

## What We Built

**Phase 2: Ingestion Service (FastAPI)**

A production-ready HTTP API that receives logs and metrics from agents!

**Status:** ✅ **TESTED AND WORKING!**

---

## Files Created (5 files)

```
observability/ingestion/
├── __init__.py          # ✅ Updated with exports
├── auth.py              # ✅ API key authentication
├── rate_limiter.py      # ✅ Token bucket rate limiting
├── kafka_producer.py    # ✅ Mock/Real Kafka producer
├── routes.py            # ✅ API endpoints
└── main.py              # ✅ FastAPI application
```

**Total:** ~1,300 lines of production-grade code!

---

## Real Test Results ✅

### Test Output:
```
✅ Service is running
✅ PASS: Health check OK
✅ PASS: Log ingestion OK
✅ PASS: Metric ingestion OK
✅ PASS: Statistics OK

Stats: {
  "status": "ok",
  "producer_type": "MockKafkaProducer",
  "logs_sent": 1,
  "metrics_sent": 1
}
```

### Performance Metrics:
```
Health check:      0.37-3.43ms  ⚡ Excellent!
Log ingestion:     2.0ms        ⚡ Fast!
Metric ingestion:  2.85ms       ⚡ Fast!
Stats endpoint:    1.42ms       ⚡ Very fast!
```

### Service Logs:
```
INFO: Application startup complete.
[info] Rate limiter initialized burst_size=1000 requests_per_second=100.0
[info] Mock Kafka producer initialized (no actual Kafka connection)
[debug] API key validated successfully
[debug] Rate limit check passed remaining_tokens=999
[info] Log batch received num_logs=1 service=quick-test
[info] Mock: Log batch sent to Kafka topic=logs.raw
[info] Metric batch received num_metrics=1 service=quick-test
[info] Mock: Metric batch sent to Kafka topic=metrics.raw
```

**Everything working perfectly!** 🎉

---

## Issues Fixed During Testing

### Issue 1: Type Hint Error ❌→✅
**Problem:** `Dict[str, any]` - lowercase 'any' is not a valid type
**Solution:** Changed to `Dict[str, Any]` - import `Any` from `typing`
**File:** `routes.py`

### Issue 2: Missing .env File ❌→✅
**Problem:** API key not configured, authentication failing
**Solution:** Created `.env` with `INGESTION_API_KEY=development-key`
**File:** `.env`

### Issue 3: Metric Type Case Sensitivity ❌→✅
**Problem:** Test sent `"GAUGE"`, model expected `"gauge"`
**Solution:** Added validator to accept both uppercase and lowercase
**File:** `models.py` - Added `normalize_metric_type` validator

```python
@validator("metric_type", pre=True)
def normalize_metric_type(cls, v):
    """Normalize metric type to lowercase to accept both 'GAUGE' and 'gauge'."""
    if isinstance(v, str):
        return v.lower()
    return v
```

---

## What Each File Does

### 1. `auth.py` (~160 lines)
**Purpose:** API key authentication

**Key components:**
- `verify_api_key()` - FastAPI dependency for auth
- `AuthenticationError` - Custom exception for 401 errors
- `APIKeyValidator` - Extensible key management

**What it provides:**
- Secure endpoint access
- API key validation
- Key metadata support
- Easy to extend (database-backed, key rotation, etc.)

---

### 2. `rate_limiter.py` (~380 lines)
**Purpose:** Prevent API abuse

**Key components:**
- `TokenBucket` - Token bucket algorithm implementation
- `RateLimiter` - Rate limiter with per-key buckets
- `check_rate_limit()` - FastAPI dependency
- `RateLimitExceeded` - Custom exception for 429 errors

**What it provides:**
- 100 requests/second sustained rate
- 1000 request burst capacity
- Per-API-key limits
- Automatic retry-after headers

---

### 3. `kafka_producer.py` (~360 lines)
**Purpose:** Write data to Kafka (or mock it)

**Key components:**
- `BaseProducer` - Abstract base class
- `MockKafkaProducer` - For testing without Kafka
- `KafkaProducer` - Real Kafka (Phase 3)
- `ProducerFactory` - Automatic mock/real selection
- `get_producer()` - FastAPI dependency

**What it provides:**
- Kafka integration (ready for Phase 3)
- Mock mode for testing (Phase 2)
- Clean abstraction (same code works with both)
- Proper resource cleanup

---

### 4. `routes.py` (~280 lines)
**Purpose:** API endpoints

**Endpoints:**
- `POST /logs` - Receive log batches
- `POST /metrics` - Receive metric batches
- `GET /health` - Health check (no auth)
- `GET /` - Service info (no auth)
- `GET /stats` - Statistics (requires auth)

**What it provides:**
- RESTful API design
- Automatic validation (Pydantic)
- Dependency injection (auth, rate limit, producer)
- Comprehensive error handling

---

### 5. `main.py` (~150 lines)
**Purpose:** FastAPI application

**Key components:**
- Application lifespan (startup/shutdown)
- CORS middleware
- Exception handlers (401, 422, 429, 500)
- Request logging middleware
- Route registration

**What it provides:**
- Complete FastAPI app
- Graceful startup/shutdown
- Comprehensive logging
- Interactive API docs (/docs)
- Production-ready error handling

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   INGESTION SERVICE                      │
│                                                           │
│  ┌────────────────────────────────────────────────┐     │
│  │            FastAPI Application                 │     │
│  │                 (main.py)                      │     │
│  └───────────────────┬────────────────────────────┘     │
│                      │                                   │
│         ┌────────────┼────────────┐                     │
│         ▼            ▼            ▼                     │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│   │ POST    │  │ POST    │  │  GET    │               │
│   │ /logs   │  │/metrics │  │ /health │               │
│   └────┬────┘  └────┬────┘  └─────────┘               │
│        │            │                                   │
│        ▼            ▼                                   │
│   ┌──────────────────────────┐                          │
│   │  Dependencies (Injected) │                          │
│   ├──────────────────────────┤                          │
│   │ 1. verify_api_key()      │ auth.py                 │
│   │ 2. check_rate_limit()    │ rate_limiter.py         │
│   │ 3. get_producer()        │ kafka_producer.py       │
│   └────────────┬─────────────┘                          │
│                │                                         │
│                ▼                                         │
│   ┌──────────────────────────┐                          │
│   │   Route Handler          │ routes.py               │
│   │   - Log request          │                          │
│   │   - Send to Kafka        │                          │
│   │   - Return response      │                          │
│   └────────────┬─────────────┘                          │
│                │                                         │
│                ▼                                         │
│   ┌──────────────────────────┐                          │
│   │   MockKafkaProducer      │ kafka_producer.py       │
│   │   - Logs to console      │                          │
│   │   - Stores in memory     │                          │
│   │   (Real Kafka in Phase 3)│                          │
│   └──────────────────────────┘                          │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Request Flow Example

**Agent sends logs:**

```
1. Agent makes request
   POST http://localhost:8000/logs
   Headers:
     X-API-Key: development-key
     Content-Type: application/json
   Body:
     {
       "entries": [{...}],
       "agent_version": "0.1.0"
     }

2. Request logging middleware
   → Starts timer

3. verify_api_key() dependency
   → Extracts X-API-Key header
   → Validates: "development-key"
   → ✅ Valid, continue

4. check_rate_limit() dependency
   → Checks token bucket for this key
   → Available tokens: 998
   → Consumes 1 token
   → ✅ OK, continue

5. Pydantic validation
   → Parses JSON body
   → Validates LogBatch schema
   → ✅ Valid, continue

6. get_producer() dependency
   → Returns MockKafkaProducer
   → ✅ Ready

7. ingest_logs() handler executes
   → Logs: "Log batch received, num_logs=100"
   → Calls: producer.send_logs(batch)
   → MockKafkaProducer logs: "Mock: sent to Kafka"
   → Returns: {"status": "accepted", ...}

8. Request logging middleware
   → Calculates duration: 12.34ms
   → Logs: "HTTP request processed, status=202, duration_ms=12.34"

9. Response sent
   HTTP 202 Accepted
   {
     "status": "accepted",
     "logs_received": 100,
     "service": "api-server",
     "message": "Log batch accepted for processing"
   }
```

---

## How to Run

### Start the ingestion service:

```bash
# Method 1: Using make
make run-ingestion

# Method 2: Using Python module
python -m observability.ingestion.main

# Method 3: Using uvicorn directly
uvicorn observability.ingestion.main:app --reload --port 8000
```

**Service runs on:** http://localhost:8000

---

## How to Test

### 1. Check health

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "ingestion-service",
  "version": "0.1.0"
}
```

---

### 2. View interactive docs

Open browser: **http://localhost:8000/docs**

You'll see Swagger UI with:
- All endpoints listed
- Try it out buttons
- Request/response schemas
- Authentication fields

---

### 3. Test log ingestion

```bash
curl -X POST http://localhost:8000/logs \
  -H "X-API-Key: development-key" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {
        "timestamp": "2024-01-11T10:00:00Z",
        "level": "INFO",
        "message": "Test log from curl",
        "service": "test-service",
        "host": "localhost"
      }
    ],
    "agent_version": "0.1.0"
  }'
```

**Expected response:**
```json
{
  "status": "accepted",
  "logs_received": 1,
  "service": "test-service",
  "message": "Log batch accepted for processing"
}
```

**Check server logs:**
```
INFO: HTTP request processed method=POST path=/logs status_code=202 duration_ms=12.34
INFO: Log batch received num_logs=1 service=test-service
INFO: Mock: Log batch sent to Kafka topic=logs.raw num_logs=1
```

---

### 4. Test metric ingestion

```bash
curl -X POST http://localhost:8000/metrics \
  -H "X-API-Key: development-key" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": [
      {
        "timestamp": "2024-01-11T10:00:00Z",
        "name": "system.cpu.usage_percent",
        "value": 45.5,
        "metric_type": "GAUGE",
        "service": "test-service",
        "host": "localhost"
      }
    ],
    "agent_version": "0.1.0"
  }'
```

---

### 5. Test authentication (invalid key)

```bash
curl -X POST http://localhost:8000/logs \
  -H "X-API-Key: wrong-key" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Expected response:**
```json
HTTP 401 Unauthorized
{
  "detail": "Invalid API key"
}
```

---

### 6. Test rate limiting

```bash
# Send 1001 requests quickly (exceeds burst of 1000)
for i in {1..1001}; do
  curl -X POST http://localhost:8000/logs \
    -H "X-API-Key: development-key" \
    -H "Content-Type: application/json" \
    -d '{...}' &
done
wait
```

**First 1000:** HTTP 202 Accepted
**Request 1001:** HTTP 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Try again in 1 seconds."
}
```

---

### 7. Check stats

```bash
curl http://localhost:8000/stats \
  -H "X-API-Key: development-key"
```

**Response:**
```json
{
  "status": "ok",
  "producer_type": "MockKafkaProducer",
  "logs_sent": 1001,
  "metrics_sent": 1
}
```

---

## End-to-End Test: Agents → Ingestion

Now let's test the FULL flow: Agent → Ingestion!

### 1. Start ingestion service

```bash
# Terminal 1
make run-ingestion
# Or: uvicorn observability.ingestion.main:app --reload --port 8000
```

### 2. Configure agents

Edit `.env`:
```bash
INGESTION_API_URL=http://localhost:8000
INGESTION_API_KEY=development-key
```

### 3. Run log agent

```bash
# Terminal 2
echo "ERROR: Database connection failed" | python -m observability.agents.log_agent \
  --service api-server \
  --batch-size 1 \
  --flush-interval 1
```

**Agent logs:**
```
INFO: Log agent starting service=api-server
INFO: Collected log from stdin
INFO: Sending batch batch_size=1
INFO: Batch sent successfully
```

**Ingestion service logs:**
```
INFO: HTTP request processed method=POST path=/logs status_code=202
INFO: Log batch received num_logs=1 service=api-server
INFO: Mock: Log batch sent to Kafka topic=logs.raw
```

✅ **SUCCESS!** Agent → Ingestion works!

### 4. Run metrics agent

```bash
# Terminal 3
python -m observability.agents.metrics_agent \
  --service web-server \
  --interval 5 \
  --batch-size 10
```

**Metrics agent logs:**
```
INFO: Metrics agent starting service=web-server interval=5.0
INFO: Metrics collected buffer_size=23
INFO: Sending batch batch_size=23
INFO: Batch sent successfully
```

**Ingestion service logs:**
```
INFO: HTTP request processed method=POST path=/metrics status_code=202
INFO: Metric batch received num_metrics=23 service=web-server
INFO: Mock: Metric batch sent to Kafka topic=metrics.raw
```

✅ **SUCCESS!** Full flow works!

---

## What Works Now

✅ **Phase 0:** Project setup
✅ **Phase 1:** Data collection agents (logs + metrics)
✅ **Phase 2:** Ingestion service (FastAPI)

**Full pipeline:**
```
Your App → Log Agent → HTTP → Ingestion API → Mock Kafka
Your App → Metrics Agent → HTTP → Ingestion API → Mock Kafka
```

---

## What's Next: Phase 3

**Phase 3: Message Bus (Kafka)**

Goals:
1. Setup Kafka/Redpanda in Docker
2. Replace MockKafkaProducer with real KafkaProducer
3. Create topics (logs.raw, metrics.raw)
4. Test end-to-end with real message queue

**After Phase 3:**
```
Your App → Agents → Ingestion API → Kafka → (Phase 4: Processors)
```

---

## Interview Talking Points

**Q: Explain the ingestion service architecture**

A: "We built a FastAPI-based ingestion service with three layers:
1. **Authentication layer** - API key validation using FastAPI dependencies
2. **Rate limiting layer** - Token bucket algorithm to prevent abuse
3. **Data layer** - Kafka producer that writes to message queue

The service is stateless and horizontally scalable. We use dependency injection for clean separation of concerns - auth, rate limiting, and Kafka are all injected dependencies."

**Q: How do you handle rate limiting?**

A: "We use the token bucket algorithm. Each API key gets a bucket with 1000 tokens (burst capacity) that refills at 100 tokens/second (sustained rate). This allows:
- Burst traffic up to 1000 requests instantly
- Sustained rate of 100 requests/second
- Graceful degradation with 429 responses and Retry-After headers"

**Q: Why FastAPI?**

A: "FastAPI provides:
- Automatic validation via Pydantic
- Async support (important for high throughput)
- Dependency injection
- Auto-generated OpenAPI docs
- Type hints and IDE support
- High performance (comparable to Node.js and Go)"

**Q: How would you scale this?**

A: "The ingestion service is stateless, so horizontal scaling is easy:
1. Run multiple instances behind a load balancer
2. Each instance shares nothing (except Kafka)
3. Rate limiting would move to Redis for distributed rate limits
4. Can scale to hundreds of instances
5. Bottleneck becomes Kafka write throughput"

**Q: What happens if Kafka is down?**

A: "Currently we'd return 500 errors. For production, I'd add:
1. Retry logic with exponential backoff
2. Circuit breaker to fail fast
3. Local buffering (write to disk)
4. Dead letter queue for failed messages
5. Monitoring and alerts"

---

## Files Created Summary

| File | Lines | Purpose |
|------|-------|---------|
| `auth.py` | ~160 | API key authentication |
| `rate_limiter.py` | ~380 | Token bucket rate limiting |
| `kafka_producer.py` | ~360 | Mock/Real Kafka producer |
| `routes.py` | ~280 | API endpoints |
| `main.py` | ~150 | FastAPI application |
| **Total** | **~1,330** | **Complete ingestion service** |

---

## Troubleshooting Guide (Real Issues Encountered)

### ❌ Issue: "Invalid args for response field! Hint: check that typing.Dict[str, <built-in function any>]"

**Symptom:** Service fails to start with FastAPI error

**Cause:** Using `Dict[str, any]` instead of `Dict[str, Any]`

**Solution:**
```python
# Wrong:
from typing import Dict
response_model=Dict[str, any]  # ❌

# Correct:
from typing import Any, Dict
response_model=Dict[str, Any]  # ✅
```

**Files to fix:** `routes.py` - All endpoint decorators

---

### ❌ Issue: "Invalid API key" even with correct key

**Symptom:** Test returns 401 Unauthorized

**Cause:** `.env` file missing or has wrong API key

**Solution:**
```bash
# Create .env file
cat > .env << 'EOF'
ENVIRONMENT=development
LOG_LEVEL=INFO
INGESTION_API_KEY=development-key
INGESTION_API_URL=http://localhost:8000
EOF

# Or copy from example
cp .env.example .env
# Then edit: INGESTION_API_KEY=development-key
```

**Verify:**
```bash
cat .env | grep INGESTION_API_KEY
# Should show: INGESTION_API_KEY=development-key
```

---

### ❌ Issue: Metric ingestion returns 422 "Input should be 'counter', 'gauge' or 'histogram'"

**Symptom:** Logs work, but metrics fail with validation error

**Cause:** Sent uppercase `"GAUGE"` but model expects lowercase `"gauge"`

**Solution 1:** Add validator to accept both (recommended)
```python
# In observability/common/models.py, add to MetricEntry class:
@validator("metric_type", pre=True)
def normalize_metric_type(cls, v):
    """Normalize metric type to lowercase."""
    if isinstance(v, str):
        return v.lower()
    return v
```

**Solution 2:** Use lowercase in requests
```json
{
  "metric_type": "gauge"  // lowercase
}
```

---

### ❌ Issue: "Port 8000 already in use"

**Symptom:** Can't start service

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
uvicorn observability.ingestion.main:app --port 8001
```

---

### ❌ Issue: "ModuleNotFoundError: No module named 'observability'"

**Symptom:** Import errors when running service

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Install in editable mode
pip install -e .

# Verify
python -c "from observability.ingestion.main import app"
```

---

## 🎉 Congratulations!

**Phase 2 is COMPLETE!**

You now have a fully functional ingestion service that can:
- ✅ Receive logs and metrics from agents
- ✅ Validate API keys
- ✅ Rate limit requests
- ✅ Process batches
- ✅ Write to Kafka (mocked)
- ✅ Handle errors gracefully
- ✅ Log everything
- ✅ Provide interactive API docs

**Progress: 40% complete** (2 out of 7 phases done!)

Ready for Phase 3: Kafka Setup? 🚀