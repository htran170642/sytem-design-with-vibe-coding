# Mini-Celery: Distributed Task Queue

A production-ready distributed task queue system built with Python, FastAPI, Redis, and asyncio. Demonstrates advanced async patterns, reliability features, and real-time WebSocket updates.

## 🎯 Features

### Core Functionality
- ✅ **Async Task Queue** - Submit tasks via HTTP API, process with workers
- ✅ **Real-time Updates** - WebSocket streaming of task progress
- ✅ **Automatic Retries** - Configurable retry logic with exponential backoff potential
- ✅ **Dead-Letter Queue** - Failed tasks moved to DLQ after max retries
- ✅ **Concurrent Processing** - Multiple workers with configurable concurrency
- ✅ **Task Status Tracking** - PENDING → RUNNING → SUCCESS/FAILED lifecycle
- ✅ **Graceful Shutdown** - Signal handling for clean worker termination

### Production-Ready Features
- 🔒 Connection pooling (50 max connections)
- 📊 Queue statistics and monitoring
- 🔄 Retry mechanism with configurable limits
- 💀 Dead-letter queue for failed tasks
- 📡 Pub/Sub for real-time events
- ⚡ High throughput

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /tasks
       ▼
┌─────────────────────────────────────────┐
│           FastAPI Server                │
│  ┌─────────────────────────────────┐   │
│  │  POST /tasks                    │   │
│  │  GET /tasks/{id}                │   │
│  │  WS /ws/tasks/{id}              │   │
│  │  GET /queue/stats               │   │
│  │  GET /queue/dead-letter         │   │
│  └─────────────────────────────────┘   │
└──────────┬──────────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │    Redis    │
    │             │
    │ • Queue     │────┐
    │ • Tasks     │    │
    │ • Pub/Sub   │    │
    └─────────────┘    │
           ▲           │
           │           │
    ┌──────┴───────────┴─────────────┐
    │                                 │
    ▼                                 ▼
┌─────────┐                    ┌─────────┐
│ Worker  │                    │ Worker  │
│ Pool    │                    │ Pool    │
│ (5x)    │                    │ (5x)    │
└─────────┘                    └─────────┘
    │                                 │
    └────────────┬────────────────────┘
                 │
                 ▼
          ┌─────────────┐
          │  WebSocket  │
          │   Clients   │
          └─────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Redis server

### Installation

```bash
# Clone repository
git clone <your-repo>
cd mini-celery

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the System

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - API Server:**
```bash
python run_api.py
# Server runs on http://localhost:8000
```

**Terminal 3 - Worker:**
```bash
python -m app.worker
# Starts 5 concurrent workers
```

**Terminal 4 - Submit Tasks:**
```bash
# Via API
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "add", "args": [10, 20]}'

# Or use interactive docs
open http://localhost:8000/docs
```

## 📖 API Reference

### Submit Task
```http
POST /tasks
Content-Type: application/json

{
  "name": "add",
  "args": [10, 20],
  "max_retries": 3
}

Response:
{
  "task_id": "uuid",
  "status": "PENDING",
  "max_retries": 3
}
```

### Check Task Status
```http
GET /tasks/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "SUCCESS",
  "result": 30,
  "error": null,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2024-12-07T10:00:00",
  "updated_at": "2024-12-07T10:00:01"
}
```

### WebSocket - Real-time Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.event, data.data);
};

// Events: connected, started, progress, completed, failed
```

### Queue Statistics
```http
GET /queue/stats

Response:
{
  "queue_length": 5,
  "queue_name": "queue:default"
}
```

### Dead-Letter Queue
```http
GET /queue/dead-letter

Response:
{
  "count": 2,
  "tasks": [...]
}
```

## 🔧 Configuration

Edit `.env` or `app/config.py`:

```python
REDIS_HOST=localhost
REDIS_PORT=6379
WORKER_CONCURRENCY=5
API_HOST=0.0.0.0
API_PORT=8000
```

## 📊 Redis Data Schema

### Queue (List)
```
Key: queue:default
Type: Redis List (FIFO)
Operations: LPUSH (enqueue), BRPOP (dequeue)
```

### Task Metadata (Hash)
```
Key: task:{task_id}
Type: Redis Hash
Fields: id, name, args, kwargs, status, result, error, 
        retry_count, max_retries, created_at, updated_at
```

### Task Events (Pub/Sub)
```
Channel: task:{task_id}:events
Type: Redis Pub/Sub
Messages: JSON events (started, progress, completed, failed)
```

### Dead-Letter Queue (List)
```
Key: queue:dead_letter
Type: Redis List
Purpose: Store failed tasks after max retries
```

## 📁 Project Structure

```
mini-celery/
├── app/
│   ├── __init__.py
│   ├── config.py          # Settings & configuration
│   ├── models.py          # Task models (Pydantic)
│   ├── utils.py           # Serialization helpers
│   ├── queue.py           # Redis queue abstraction
│   ├── tasks.py           # Task registry & definitions
│   ├── worker.py          # Worker process
│   └── api.py             # FastAPI server
├── tests/
│   ├── conftest.py        # Pytest fixtures
│   ├── test_queue.py      # Unit tests
│   ├── test_integration.py # Integration tests
│   └── test_load.py       # Load/performance tests
├── websocket_client.html  # Demo WebSocket client
├── requirements.txt
├── pytest.ini
└── README.md
```

## 🚧 Future Enhancements

- [ ] Task priorities (multiple queues)
- [ ] Periodic tasks (cron-like scheduling)
- [ ] Task chaining/workflows
- [ ] Result backends (PostgreSQL/MongoDB)
- [ ] Monitoring dashboard
- [ ] Rate limiting per task type
- [ ] Task cancellation
- [ ] Distributed locks
- [ ] Metrics export (Prometheus)
- [ ] Docker deployment

## Technical Deep Dives

### Q: Walk me through the task lifecycle

**Answer:**
```
1. Client POSTs to /tasks
2. API creates Task object, generates UUID
3. Task saved to Redis hash (task:{id})
4. Task ID pushed to Redis list (queue:default)
5. Worker BRPOPs from queue (blocking, non-busy-wait)
6. Worker updates status to RUNNING
7. Worker publishes "started" event to Redis Pub/Sub
8. Worker executes task function
9. On success: status→SUCCESS, result stored, "completed" event
10. On failure: check retry count
    - If retries left: requeue task, increment counter
    - If max retries: move to dead-letter queue
11. WebSocket clients receive all events in real-time
```

### Q: Explain your async patterns

**1. Fire-and-Forget (create_task)**
```python
# Use case: Background worker loops
workers = [asyncio.create_task(worker_loop(i)) for i in range(5)]
# Workers run independently, don't block each other
```

**2. Wait-for-All (gather)**
```python
# Use case: Bulk task submission
await asyncio.gather(*[enqueue_task(t) for t in tasks])
# All must complete before continuing
```

**3. Graceful Shutdown**
```python
# Signal handler sets flag + event
signal.signal(signal.SIGTERM, lambda: shutdown_event.set())

# Workers check flag in loop
while self.running:
    task_id = await pop_task(timeout=2)  # Short timeout
    if task_id:
        await handle_task(task_id)
# Finish current tasks before exiting
```

**4. WebSocket + Pub/Sub Bridge**
```python
pubsub = await redis.subscribe(f"task:{id}:events")
async for message in pubsub.listen():
    await websocket.send_json(message)
# Async iteration bridges two systems
```

### Q: How did you handle the connection pool issue?

**Problem:**
```python
# 100 concurrent gather() calls
await asyncio.gather(*[enqueue(t) for t in tasks])
# Error: "Too many connections" - pool exhausted
```

**Solution:**
```python
# 1. Increased pool size: 10 → 50
max_connections=50

# 2. Batch processing
batches = [tasks[i:i+20] for i in range(0, len(tasks), 20)]
for batch in batches:
    await asyncio.gather(*[enqueue(t) for t in batch])

# Result: 800 tasks/sec without errors
```

### Q: Why Redis over other message queues?

**Redis Pros:**
- Simple setup (single dependency)
- Multiple data structures (list, hash, pub/sub)
- Atomic operations (LPUSH/BRPOP)
- Very fast (in-memory)
- Good for 10k-100k tasks/day

**Trade-offs:**
- No guaranteed delivery (vs RabbitMQ)
- No message ordering guarantees (vs Kafka)
- Single-threaded (bottleneck at high scale)
- In-memory only (unless using persistence)

**When I'd switch:**
- RabbitMQ: Need message acknowledgment, complex routing
- Kafka: Need event log, message replay, 1M+ events/day
- SQS: AWS ecosystem, don't want to manage infrastructure

### Q: How would you add task priorities?

**Approach 1: Multiple Queues**
```python
queues = ["queue:high", "queue:medium", "queue:low"]

# Worker checks high priority first
for queue_name in queues:
    task_id = await redis.brpop(queue_name, timeout=1)
    if task_id:
        break
```

**Approach 2: Redis Sorted Set**
```python
# Score = priority (higher = more urgent)
await redis.zadd("queue:priority", {task_id: priority})

# Pop highest priority
task_id = await redis.zpopmax("queue:priority")
```

**Trade-off:**
- Multiple queues: Simpler, but can starve low priority
- Sorted set: Fair, but more complex, no blocking pop

### Q: What would break at 1M tasks/hour?

**Bottlenecks:**

1. **Single Redis Instance**
   - Solution: Redis Cluster with sharding
   
2. **Single Worker Process**
   - Solution: Multiple machines, each running workers
   
3. **Task Status Queries** (1M HGETALL/hour)
   - Solution: Cache in PostgreSQL, query DB not Redis
   
4. **WebSocket Connections** (10k+ concurrent)
   - Solution: Dedicated WS server, use Redis Streams for history

**Scaling Architecture:**
```
Load Balancer
  ↓
API Servers (10x) → Redis Cluster (5 nodes)
                    ↓
                  Worker Pools (50 machines × 5 workers)
                    ↓
                  PostgreSQL (task results)
```

## Other docs
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Command snippets & usage
- [ARCHITECTURE.md](ARCHITECTURE.md) - Deep dive into design