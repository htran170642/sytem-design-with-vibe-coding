# Mini-Celery Quick Reference

## Start the System
```bash
redis-server                    # Terminal 1
python run_api.py               # Terminal 2
python -m app.worker            # Terminal 3
```

## Submit Tasks
```bash
# cURL
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "add", "args": [10, 20]}'

# Python
import httpx
response = httpx.post("http://localhost:8000/tasks", 
                      json={"name": "add", "args": [10, 20]})
```

## Check Status
```bash
curl http://localhost:8000/tasks/{task_id}
```

## WebSocket (JavaScript)
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Redis Commands
```bash
redis-cli

LLEN queue:default              # Queue length
HGETALL task:{id}               # Task details
LRANGE queue:dead_letter 0 -1   # Failed tasks
KEYS task:*                     # All tasks
```

## Run Tests
```bash
pytest tests/ -v                # All tests
python -m tests.test_load       # Load tests
python benchmark.py             # Performance
```

## Key Files
- `app/api.py` - HTTP/WebSocket endpoints
- `app/worker.py` - Task processing
- `app/queue.py` - Redis operations
- `app/tasks.py` - Task definitions
- `app/models.py` - Data models

## Available Tasks
- `add` - Add two numbers
- `multiply` - Multiply two numbers
- `sleep` - Sleep for N seconds
- `long_task` - Multi-step task with progress
- `failing_task` - Always fails (testing)

## Environment Variables
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
WORKER_CONCURRENCY=5
API_PORT=8000
```