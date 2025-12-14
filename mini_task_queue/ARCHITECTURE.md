# Mini-Celery Architecture Deep Dive

## System Components

### 1. API Server (FastAPI)
**Responsibilities:**
- Accept task submissions
- Query task status
- Stream real-time updates via WebSocket
- Provide queue statistics

**Endpoints:**
```
POST   /tasks              → Submit new task
GET    /tasks/{id}         → Get task status
DELETE /tasks/{id}         → Delete task
WS     /ws/tasks/{id}      → Real-time updates
GET    /queue/stats        → Queue statistics
GET    /queue/dead-letter  → Failed tasks
POST   /tasks/{id}/retry   → Manual retry
```

### 2. Redis (Message Broker + Storage)
**Data Structures:**

```
┌─────────────────────────────────────────┐
│              REDIS                      │
├─────────────────────────────────────────┤
│                                         │
│  Lists (Queues):                        │
│  • queue:default                        │
│  • queue:dead_letter                    │
│                                         │
│  Hashes (Task Metadata):                │
│  • task:{uuid} → {                      │
│      id, name, args, kwargs,            │
│      status, result, error,             │
│      retry_count, max_retries,          │
│      created_at, updated_at             │
│    }                                    │
│                                         │
│  Pub/Sub (Events):                      │
│  • task:{uuid}:events                   │
│                                         │
└─────────────────────────────────────────┘
```

### 3. Worker Process
**Architecture:**

```
┌────────────────────────────────────────┐
│         Worker Process                 │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────┐  ┌──────────┐          │
│  │ Worker-0 │  │ Worker-1 │          │
│  │  Loop    │  │  Loop    │   ...    │
│  └────┬─────┘  └────┬─────┘          │
│       │             │                 │
│       └──────┬──────┘                 │
│              │                        │
│         BRPOP queue                   │
│              │                        │
│              ▼                        │
│       ┌─────────────┐                │
│       │ Task Exec   │                │
│       │ + Retry     │                │
│       │ + Events    │                │
│       └─────────────┘                │
│                                       │
└───────────────────────────────────────┘
```

## Data Flow Diagrams

### Task Submission Flow

```
Client                API                Redis               Worker
  │                    │                   │                   │
  │  POST /tasks       │                   │                   │
  ├───────────────────>│                   │                   │
  │                    │                   │                   │
  │                    │  HSET task:{id}   │                   │
  │                    ├──────────────────>│                   │
  │                    │                   │                   │
  │                    │  LPUSH queue      │                   │
  │                    ├──────────────────>│                   │
  │                    │                   │                   │
  │  {task_id}         │                   │                   │
  │<───────────────────┤                   │                   │
  │                    │                   │                   │
  │                    │                   │  BRPOP queue      │
  │                    │                   │<──────────────────┤
  │                    │                   │                   │
  │                    │                   │  task_id          │
  │                    │                   ├──────────────────>│
  │                    │                   │                   │
```

### Task Processing Flow

```
Worker              Redis               Pub/Sub           WebSocket Client
  │                   │                   │                      │
  │ HGETALL task:id   │                   │                      │
  ├──────────────────>│                   │                      │
  │                   │                   │                      │
  │ task data         │                   │                      │
  │<──────────────────┤                   │                      │
  │                   │                   │                      │
  │ HSET status=RUN   │                   │                      │
  ├──────────────────>│                   │                      │
  │                   │                   │                      │
  │ PUBLISH started   │                   │                      │
  ├──────────────────────────────────────>│                      │
  │                   │                   │                      │
  │                   │                   │  {event: started}    │
  │                   │                   ├─────────────────────>│
  │                   │                   │                      │
  │ execute()         │                   │                      │
  ├───┐               │                   │                      │
  │   │               │                   │                      │
  │<──┘               │                   │                      │
  │                   │                   │                      │
  │ HSET result       │                   │                      │
  ├──────────────────>│                   │                      │
  │                   │                   │                      │
  │ PUBLISH completed │                   │                      │
  ├──────────────────────────────────────>│                      │
  │                   │                   │                      │
  │                   │                   │  {event: completed}  │
  │                   │                   ├─────────────────────>│
```

### Retry Flow

```
Worker              Redis
  │                   │
  │ Task fails        │
  ├───┐               │
  │   │               │
  │<──┘               │
  │                   │
  │ retry_count < max?│
  ├───┐               │
  │   │ YES           │
  │<──┘               │
  │                   │
  │ HINCRBY retry_cnt │
  ├──────────────────>│
  │                   │
  │ LPUSH queue       │
  ├──────────────────>│
  │                   │
  
  (Task requeued, another worker picks it up)
  
  
  If retry_count >= max:
  
  │ LPUSH dead_letter │
  ├──────────────────>│
  │                   │
  │ HSET status=FAIL  │
  ├──────────────────>│
```

## Concurrency Model

### Worker Concurrency

```python
# Single worker process with N coroutines

async def main():
    workers = [
        asyncio.create_task(worker_loop(0)),
        asyncio.create_task(worker_loop(1)),
        asyncio.create_task(worker_loop(2)),
        asyncio.create_task(worker_loop(3)),
        asyncio.create_task(worker_loop(4)),
    ]
    await asyncio.gather(*workers)
```

**Benefits:**
- All workers share same event loop
- No GIL contention (I/O-bound)
- Efficient context switching
- Easy inter-worker communication

### Scaling Pattern

```
┌─────────────────────────────────────┐
│        Load Balancer (nginx)        │
└──────────┬──────────────────────────┘
           │
     ┌─────┴──────┐
     │            │
     ▼            ▼
┌─────────┐  ┌─────────┐
│  API-1  │  │  API-2  │  (Stateless)
└────┬────┘  └────┬────┘
     │            │
     └─────┬──────┘
           │
           ▼
    ┌─────────────┐
    │Redis Cluster│
    └──────┬──────┘
           │
     ┌─────┴──────┬─────────┐
     │            │         │
     ▼            ▼         ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│Worker-1 │  │Worker-2 │  │Worker-3 │
│Pool (5) │  │Pool (5) │  │Pool (5) │
└─────────┘  └─────────┘  └─────────┘
```

## Performance Characteristics

### Bottlenecks & Solutions

**1. Redis Connection Pool**
- Problem: 100+ concurrent operations → pool exhaustion
- Solution: Increased to 50 connections, batching
- Alternative: Redis pipeline for bulk ops

**2. Task Processing Rate**
- Current: 5 workers
- Bottleneck: Task execution time (not framework)
- Solution: More workers, task-specific pools

**3. WebSocket Scalability**
- Problem: Each WS holds a Pub/Sub connection
- Current: OK for 100s of connections
- Solution at scale: Dedicated WebSocket server with Redis Streams

## Security Considerations

**Current:**
- No authentication (demo project)
- CORS enabled for all origins
- No rate limiting

**Production Additions:**
- API key authentication
- JWT tokens for WebSocket
- Rate limiting (per user/IP)
- Input validation (already has Pydantic)
- Redis AUTH
- TLS for Redis connections
- Network policies (firewall)

## Monitoring Points

**Metrics to Track:**

```python
# Queue metrics
- queue_length: Current tasks waiting
- dead_letter_count: Failed tasks
- enqueue_rate: Tasks/sec submitted
- processing_rate: Tasks/sec completed

# Worker metrics  
- active_workers: Currently processing
- idle_workers: Waiting for tasks
- task_duration_p50/p95/p99: Latency percentiles
- error_rate: Failed tasks/total

# System metrics
- redis_connections: Pool utilization
- memory_usage: Redis memory
- cpu_usage: Worker processes
```

## Failure Scenarios

### Worker Crash
```
Worker dies mid-task → Task stays in RUNNING
Solution: Visibility timeout (watchdog requeues stuck tasks)
```

### Redis Crash
```
All state lost → Need persistence
Solution: Redis AOF/RDB, or external DB for critical tasks
```

### Network Partition
```
Worker can't reach Redis → Tasks stuck
Solution: Health checks, exponential backoff, circuit breaker
```

### API Server Crash
```
No impact on workers (stateless)
Solution: Load balancer auto-recovery
```