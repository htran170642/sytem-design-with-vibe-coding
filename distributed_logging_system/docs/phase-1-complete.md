# Phase 1 Complete ✅

## What We Built

Phase 1 focused on **Data Collection Agents** - the components that collect logs and metrics from applications and send them to the ingestion service.

---

## Files Created

### 1. `observability/common/models.py`
**Purpose:** Data models for logs, metrics, and batches

**What it contains:**
- `LogEntry` - Structure for a single log line
- `MetricEntry` - Structure for a single metric data point
- `LogBatch` - Collection of logs sent together
- `MetricBatch` - Collection of metrics sent together
- `LogLevel` enum - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `MetricType` enum - COUNTER, GAUGE, HISTOGRAM

**Key features:**
- Pydantic models for validation and type safety
- Automatic timestamp handling
- JSON serialization built-in
- Field validation (e.g., message can't be empty)

**Example usage:**
```python
from observability.common.models import LogEntry, LogLevel

log = LogEntry(
    message="User login successful",
    level=LogLevel.INFO,
    service="auth-service",
    host="web-01",
    labels={"user_id": "12345"}
)
```

---

### 2. `observability/common/retry.py`
**Purpose:** Retry logic with exponential backoff for handling failures

**What it contains:**
- `RetryConfig` - Configure retry behavior
- `retry_async()` - Retry async functions
- `retry_sync()` - Retry sync functions
- `CircuitBreaker` - Prevent cascading failures

**Key features:**
- Exponential backoff (1s → 2s → 4s → 8s)
- Jitter to prevent thundering herd problem
- Configurable max retries and delays
- Circuit breaker pattern for dead services

**Example usage:**
```python
from observability.common.retry import retry_async, RetryConfig

# Automatically retries on failure
await retry_async(
    send_to_api,
    data=my_data,
    config=RetryConfig(max_retries=3)
)
```

**Why exponential backoff?**
```
Attempt 1: Fail → Wait 1.0s
Attempt 2: Fail → Wait 2.0s
Attempt 3: Fail → Wait 4.0s
Attempt 4: Success! ✅
```

**Why jitter?**
Without jitter, all clients retry at the exact same time, overwhelming the server.
With jitter, retries are spread out randomly.

---

### 3. `observability/agents/log_agent.py`
**Purpose:** Collect logs from files or stdin and send to ingestion API

**What it contains:**
- `LogAgent` class - Main log collection agent
- File tailing (like `tail -f`)
- Stdin reading (for piping)
- Batching and buffering
- Retry logic integration
- Graceful shutdown handling

**Key features:**
- **Flexible input:** Read from log files OR stdin
- **Batching:** Sends 100 logs at once (configurable)
- **Smart flushing:** By size (100 logs) OR time (5 seconds)
- **Buffer management:** Holds up to 10,000 logs in memory
- **Log level detection:** Automatically parses ERROR, WARNING, etc.
- **Signal handling:** Graceful shutdown on Ctrl+C

**How it works:**
```
Application → log file → LogAgent → [Batch 100 logs] → Ingestion API
     │                       ▲
     │                       │
     └─ writes logs      tails file
```

**Usage examples:**
```bash
# Tail a log file
python -m observability.agents.log_agent \
    --service api-server \
    --file /var/log/app.log

# Read from stdin (pipe from another program)
echo "ERROR: Database timeout" | \
    python -m observability.agents.log_agent --service test

# Custom batching
python -m observability.agents.log_agent \
    --service worker \
    --file /var/log/worker.log \
    --batch-size 500 \
    --flush-interval 10.0
```

**Architecture:**
```python
# Two concurrent operations:
asyncio.gather(
    _collect_logs(),      # Continuously reads logs
    _flush_periodically() # Flushes every 5 seconds
)
```

---

### 4. `observability/agents/metrics_agent.py`
**Purpose:** Collect system metrics (CPU, memory, disk, network) and send to ingestion API

**What it contains:**
- `MetricsAgent` class - Main metrics collection agent
- CPU usage collection (overall + per-core)
- Memory usage collection (RAM + swap)
- Disk usage collection (per partition)
- Network I/O collection (with rate calculation)

**Metrics collected:**

**CPU:**
- `system.cpu.usage_percent` - Overall CPU usage (%)
- `system.cpu.count` - Number of CPU cores
- `system.cpu.load_average` - System load (1min, 5min, 15min)
- Per-core usage (optional with `--per-cpu`)

**Memory:**
- `system.memory.total_bytes` - Total RAM
- `system.memory.used_bytes` - Used RAM
- `system.memory.available_bytes` - Available RAM
- `system.memory.usage_percent` - RAM usage (%)
- `system.swap.total_bytes` - Swap size
- `system.swap.used_bytes` - Swap used
- `system.swap.usage_percent` - Swap usage (%)

**Disk:**
- `system.disk.total_bytes` - Total disk space (per partition)
- `system.disk.used_bytes` - Used disk space
- `system.disk.free_bytes` - Free disk space
- `system.disk.usage_percent` - Disk usage (%)

**Network:**
- `system.network.bytes_sent` - Cumulative bytes sent (COUNTER)
- `system.network.bytes_received` - Cumulative bytes received (COUNTER)
- `system.network.bytes_sent_per_second` - Send rate (GAUGE)
- `system.network.bytes_received_per_second` - Receive rate (GAUGE)

**Key features:**
- **Periodic collection:** Every 10 seconds (configurable)
- **Batching:** Sends 50 metrics at once
- **Rate calculation:** Converts cumulative counters to rates
- **Labels/dimensions:** Distinguishes metrics by partition, CPU core, etc.
- **Configurable:** Enable/disable disk, network, per-CPU metrics

**Usage examples:**
```bash
# Basic usage - collect every 10 seconds
python -m observability.agents.metrics_agent --service api-server

# Collect more frequently (every 5 seconds)
python -m observability.agents.metrics_agent \
    --service worker \
    --interval 5.0

# Include per-CPU metrics
python -m observability.agents.metrics_agent \
    --service api \
    --per-cpu

# Minimal (only CPU + memory)
python -m observability.agents.metrics_agent \
    --service minimal \
    --no-disk \
    --no-network
```

**Collection flow:**
```
Every 10 seconds:
┌──────────────────────┐
│ Collect CPU metrics  │ → 4 metrics
├──────────────────────┤
│ Collect Memory       │ → 7 metrics
├──────────────────────┤
│ Collect Disk         │ → 8 metrics (2 partitions × 4)
├──────────────────────┤
│ Collect Network      │ → 4 metrics
└──────────────────────┘
Total: ~23 metrics per collection

After 2 collections (20 seconds): 46 metrics
Buffer size = 50 → FLUSH! Send to API
```

**Metric Types:**
- **COUNTER:** Always increases (e.g., total bytes sent)
- **GAUGE:** Can go up/down (e.g., CPU %, memory used)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Your Application                     │
│  - Writes logs to file                                   │
│  - Consumes CPU, memory, disk, network                  │
└──────────────┬────────────────────┬─────────────────────┘
               │                    │
               ▼                    ▼
    ┌──────────────────┐  ┌──────────────────┐
    │   Log Agent      │  │  Metrics Agent   │
    │  - Tails file    │  │  - Collects CPU  │
    │  - Batches       │  │  - Collects Mem  │
    │  - Buffers       │  │  - Collects Disk │
    └────────┬─────────┘  └────────┬─────────┘
             │                     │
             │  Batch of 100 logs  │  Batch of 50 metrics
             │                     │
             ▼                     ▼
    ┌─────────────────────────────────────┐
    │     Ingestion API (Phase 2)         │
    │  POST /logs                          │
    │  POST /metrics                       │
    └─────────────────────────────────────┘
```

---

## Key Concepts Learned

### 1. Batching
**Problem:** Sending 1 log = 1 HTTP request. For 1000 logs = 1000 requests (slow!)

**Solution:** Send 100 logs in 1 request = 10 requests (10x faster!)

```python
# Bad:
for log in logs:
    send(log)  # 1000 HTTP requests

# Good:
batch = logs[0:100]
send(batch)  # 1 HTTP request for 100 logs
```

### 2. Exponential Backoff
**Problem:** If API is down, retrying immediately wastes resources.

**Solution:** Wait longer between each retry.

```
Try 1 → Fail → Wait 1s
Try 2 → Fail → Wait 2s
Try 3 → Fail → Wait 4s
Try 4 → Success!
```

### 3. Graceful Shutdown
**Problem:** User presses Ctrl+C, buffered data is lost.

**Solution:** Catch signal, flush buffer, then exit.

```python
signal.SIGINT received (Ctrl+C)
→ Stop collecting new data
→ Flush remaining 50 logs from buffer
→ Close connections
→ Exit cleanly
```

### 4. Async I/O
**Problem:** Waiting for file I/O blocks the entire program.

**Solution:** Use async/await to do multiple things concurrently.

```python
# These run at the same time:
await asyncio.gather(
    collect_logs(),    # Reading from file
    flush_timer(),     # Flushing every 5 seconds
)
```

### 5. Circuit Breaker
**Problem:** Service is down, but we keep trying and failing (waste resources).

**Solution:** After 5 failures, stop trying for 60 seconds.

```
Fail 1, 2, 3, 4, 5 → Circuit OPEN
For next 60 seconds: Fail immediately (don't even try)
After 60 seconds: Try once → Success? Close circuit
```

---

## Testing What We Built

Although we haven't built the ingestion API yet (Phase 2), we can test the agents:

### Test Log Agent (without API)

```bash
# Create a test script that prints to stdout
cat > test_app.py << 'EOF'
import time
for i in range(10):
    print(f"[INFO] Log message {i}")
    time.sleep(1)
EOF

# Pipe output to log agent
python test_app.py | python -m observability.agents.log_agent --service test

# You'll see:
# - Agent starts
# - Collects logs
# - Tries to send to API (will fail since we haven't built it yet)
# - Retries with exponential backoff
```

### Test Metrics Agent (without API)

```bash
# Run metrics agent
python -m observability.agents.metrics_agent --service test --interval 5

# You'll see:
# - Agent starts
# - Collects metrics every 5 seconds
# - Logs: "Metrics collected, buffer_size=23"
# - Tries to send (will fail without API)
```

---

## File Locations Summary

```
observability/
├── common/
│   ├── config.py         # (From Phase 0)
│   ├── logger.py         # (From Phase 0)
│   ├── models.py         # ✅ NEW - Data models
│   └── retry.py          # ✅ NEW - Retry logic
└── agents/
    ├── log_agent.py      # ✅ NEW - Log collector
    └── metrics_agent.py  # ✅ NEW - Metrics collector
```

---

## Production Considerations

### What We Did Well:
✅ Batching for efficiency
✅ Retry logic with exponential backoff
✅ Graceful shutdown (no data loss)
✅ Buffer overflow protection
✅ Configurable via command-line arguments
✅ Structured logging for debugging
✅ Type safety with Pydantic

### What We'd Need for Real Production:
⚠️ **Persistent storage:** Currently drops logs if all retries fail. Should write to disk.
⚠️ **Compression:** Compress batches before sending to save bandwidth.
⚠️ **Encryption:** TLS/SSL for secure transmission.
⚠️ **Monitoring:** Monitor the agents themselves (are they running? buffer size?)
⚠️ **Resource limits:** Set memory limits to prevent OOM.
⚠️ **Log rotation:** Handle log file rotation gracefully.
⚠️ **Sampling:** For very high-volume systems, sample logs/metrics.

---

## Interview Talking Points

**Q: How does the log agent handle high log volume?**
A: 
1. Batching - sends 100 logs at once instead of one-by-one
2. Buffering - holds up to 10,000 logs in memory
3. Buffer overflow protection - drops oldest if buffer full
4. For production, would add disk-based buffering and compression

**Q: What happens if the ingestion API is down?**
A:
1. Retry with exponential backoff (1s, 2s, 4s delays)
2. Jitter prevents thundering herd
3. After max retries, logs error and drops batch
4. Could implement circuit breaker to stop trying temporarily
5. Production would persist to disk instead of dropping

**Q: How do you handle metric rate calculation?**
A:
Network bytes are cumulative counters, so:
```python
bytes_sent_rate = (current - previous) / time_delta
Example: (2000 - 1000) / 600 = 1.67 bytes/sec
```

**Q: Why use async/await?**
A:
1. Handle I/O concurrently (file reading + HTTP sending)
2. More efficient than threads for I/O-bound tasks
3. Can run collector and flusher simultaneously
4. Non-blocking so agent stays responsive

**Q: How would you scale this to 1000 hosts?**
A:
1. Each host runs its own agent (distributed collection)
2. Agents send to load-balanced ingestion API
3. Kafka handles backpressure if ingestion is slow
4. Could add local aggregation before sending
5. Consider sampling for extremely high volume

---

## Next Steps: Phase 2

Now that we can **collect** data, we need to **receive** it!

**Phase 2: Ingestion Service (FastAPI)**
- Build HTTP API with `POST /logs` and `POST /metrics`
- Add rate limiting
- Add API key authentication
- Validate incoming data
- Write to Kafka for processing

Ready to continue? 🚀