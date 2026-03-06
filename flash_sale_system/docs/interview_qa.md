# Flash Sale System — Interview Q&A

Covers all 8 topics from the Final Interview Readiness Checklist.
Each question includes an English answer and a Vietnamese answer.

---

## Q1: Why is database locking bad under high concurrency?

### English

DB row locking (`SELECT ... FOR UPDATE`) serializes access at the row level. Only one transaction holds the lock at a time — every other request queues behind it. Under 100k concurrent requests:

- **Lock contention**: requests pile up waiting for the lock to release
- **Latency spikes**: each transaction holds the lock for the duration of a network round-trip to the DB, so queue time compounds
- **Timeout cascades**: requests waiting too long get killed, causing errors even when the item is still in stock
- **Deadlock risk**: multiple transactions locking different rows in different orders can deadlock, forcing PostgreSQL to roll back one side
- **No horizontal scale**: DB locks cannot be distributed across multiple nodes trivially

We replace DB locking with a Redis Lua script — atomic within Redis's single-threaded executor, sub-millisecond, no transactions, no rollback log.

### Vietnamese

DB row lock (`SELECT ... FOR UPDATE`) buộc tất cả request phải xếp hàng — chỉ 1 transaction giữ lock tại một thời điểm. Với 100k request đồng thời:

- **Lock contention**: hàng nghìn request chờ nhau, throughput sụp đổ
- **Latency tăng**: mỗi transaction giữ lock suốt quá trình round-trip đến DB
- **Timeout**: request chờ quá lâu bị kill, user nhận lỗi dù hàng còn
- **Deadlock**: nhiều transaction lock row theo thứ tự khác nhau → deadlock → rollback
- **Không scale ngang**: lock logic không thể phân tán dễ dàng sang nhiều DB node

Giải pháp: dùng Redis Lua script — atomic trong single-threaded executor của Redis, dưới 1ms, không cần transaction.

---

## Q2: How does the Redis Lua script guarantee atomicity?

### English

Redis is **single-threaded** — all commands go through one event loop sequentially. When Redis receives `EVALSHA`, it treats the entire Lua script as one indivisible command:

- No other client command can execute between lines of the script
- The script either runs completely or not at all — no partial execution
- This eliminates the check-then-act race condition you get with separate `GET` + `SET` calls

**Without Lua (race condition):**
```
Client A: GET stock → 1
Client B: GET stock → 1   ← interleaved
Client A: SET stock 0     ← oversell!
Client B: SET stock 0     ← oversell!
```

**With Lua (atomic):**
```lua
local stock = redis.call('GET', KEYS[1])
if tonumber(stock) > 0 then
    redis.call('DECR', KEYS[1])
    return 1   -- success
end
return 0       -- sold out
-- Nothing can interleave here
```

### Vietnamese

Redis chạy trên **1 thread duy nhất** — mọi command đi qua 1 event loop tuần tự. Khi Redis nhận `EVALSHA`, toàn bộ Lua script được coi là 1 command không thể chia nhỏ:

- Không có request nào khác chen vào giữa các dòng script
- Script chạy toàn bộ hoặc không chạy gì — không có trạng thái "chạy một nửa"
- Loại bỏ hoàn toàn race condition của pattern `GET` + `SET` riêng lẻ

Đây là lý do tại sao hệ thống flash sale không bao giờ oversell dù có 100k request đồng thời — Lua script đảm bảo mỗi lần decrement là atomic.

---

## Q3: How does your idempotency strategy work?

### English

Two independent layers, each protecting a different failure scenario:

**Layer 1 — Redis (API hot path):**
```
SET idempotency:{user_id}:{key}  "pending"  NX  EX 86400
```
- `NX`: only set if key does not exist — first request wins
- `EX 86400`: auto-expires after 24h — no memory leak
- If `SET NX` returns `None` → duplicate → read cached `order_id` → return immediately without touching stock or stream
- After successful enqueue → overwrite `"pending"` with the real `order_id`

**Layer 2 — PostgreSQL (worker safety net):**
```sql
INSERT INTO orders (order_id, user_id, product_id, ...)
ON CONFLICT (user_id, product_id) DO NOTHING
```
- `UNIQUE(user_id, product_id)` enforces one purchase per user
- `ON CONFLICT DO NOTHING` makes duplicate inserts a safe no-op
- Worker returns `True` (inserted) or `False` (duplicate) — never crashes on duplicates

**Why both layers?**

| Scenario | Layer 1 | Layer 2 |
|---|---|---|
| Client retries same request | Caught at API | — |
| Worker redelivers after crash | Redis TTL may have expired | ON CONFLICT DO NOTHING |
| Redis restarts, loses key | Not protected | Caught by DB constraint |

### Vietnamese

Hai layer độc lập, mỗi layer bảo vệ một failure scenario khác nhau:

**Layer 1 — Redis (hot path):**
- `SET NX` với user-scoped key: `idempotency:{user_id}:{key}`
- Request đầu tiên claim key, set value = `"pending"`
- Request trùng lặp: `SET NX` trả về `None` → đọc cached `order_id` → trả về ngay, không động vào stock hay stream
- Sau khi enqueue thành công → ghi đè `"pending"` bằng `order_id` thực

**Layer 2 — PostgreSQL (safety net):**
- `UNIQUE(user_id, product_id)` + `ON CONFLICT DO NOTHING`
- Worker xử lý lại message sau crash → INSERT duplicate → safe no-op
- `insert_order()` trả về `True/False` thay vì throw exception

Hai layer bổ sung cho nhau: Redis bắt duplicate nhanh trên hot path, PostgreSQL bắt duplicate khi Redis key đã expire hoặc Redis restart.

---

## Q4: What is the eventual consistency tradeoff in your system?

### English

**Strong consistency**: API returns "accepted" only after the order is confirmed written to PostgreSQL.

**Eventual consistency** (our approach): API returns "accepted" as soon as the order is enqueued in the Redis Stream. PostgreSQL is updated asynchronously by the worker.

**Why we chose it:**
- Redis operations are sub-millisecond → P99 latency stays under 10ms
- PostgreSQL writes on the critical path would add 5–20ms per request and make DB the throughput bottleneck

**Tradeoffs accepted:**
- Brief inconsistency window: order exists in Redis but not yet in PostgreSQL (milliseconds under normal load)
- More complexity: need idempotency, retry logic, DLQ, and ACK-after-write semantics

**Guarantees we provide despite eventual consistency:**
- Stock is atomically reserved in Redis at request time — no overselling
- Order event is durably persisted in the Redis Stream (AOF) — no data loss
- Worker will eventually process every message — guaranteed delivery via consumer groups

### Vietnamese

**Strong consistency**: API chỉ trả về "accepted" sau khi ghi DB thành công.

**Eventual consistency** (cách chúng ta dùng): API trả về "accepted" ngay khi enqueue vào Redis Stream. PostgreSQL được cập nhật async bởi worker.

**Tại sao chọn eventual consistency:**
- Redis sub-millisecond → P99 latency dưới 10ms
- Ghi DB trên critical path sẽ thêm 5–20ms/request và biến DB thành bottleneck

**Đánh đổi chấp nhận:**
- Inconsistency window ngắn: order có trong Redis nhưng chưa có trong DB (vài milliseconds)
- Phức tạp hơn: cần idempotency, retry, DLQ, XACK-after-write

**Đảm bảo vẫn giữ được:**
- Stock được reserve atomic trong Redis — không oversell
- Stream entry được persist bằng AOF — không mất data
- Worker đảm bảo xử lý mọi message qua consumer group

---

## Q5: What is the hot-key problem and how do you solve it?

### English

**Problem:** In Redis Cluster, each key maps to exactly one hash slot, which lives on one node. In a flash sale, every request hits the same key (`stock:product-A`). That single node becomes a bottleneck regardless of how many nodes are in the cluster — adding more nodes does not help because the load is not distributed.

```
Node 1: stock:product-A  ← 100k RPS  (overloaded)
Node 2: (idle)
Node 3: (idle)
```

**Solutions:**

**1. Stock sharding** — split one key into N shards:
```
stock:product-A:shard-0  →  2500 items  (Node 1)
stock:product-A:shard-1  →  2500 items  (Node 2)
stock:product-A:shard-2  →  2500 items  (Node 3)
stock:product-A:shard-3  →  2500 items  (Node 4)
```
Route each request to a random shard. Tradeoff: aggregating total stock requires reading all shards.

**2. In-process local cache (early rejection):**
Each API pod caches stock = 0 locally. When cache says sold out, reject before hitting Redis at all. Drastically reduces hot-key load.

**3. Probabilistic load shedding:**
When Redis latency spikes, randomly reject a percentage of incoming requests before they reach Redis.

### Vietnamese

**Vấn đề:** Trong Redis Cluster, mỗi key map đến 1 hash slot trên 1 node. Flash sale khiến tất cả request hit cùng key `stock:product-A` → 1 node duy nhất bị quá tải dù có bao nhiêu node trong cluster.

**Giải pháp:**

**1. Stock sharding:** chia 1 key thành N shard, phân tán qua nhiều node. Mỗi request route ngẫu nhiên đến 1 shard. Tradeoff: cần đọc tất cả shard để biết tổng stock.

**2. Local cache tại API pod:** cache `stock = 0` in-memory tại mỗi pod. Khi cache báo sold out → reject ngay, không gọi Redis. Giảm drastically tải hot-key.

**3. Probabilistic load shedding:** khi Redis latency tăng cao, từ chối ngẫu nhiên % request trước khi chạm Redis.

---

## Q6: How do you scale Redis?

### English

**Step 1 — Vertical scaling:** increase RAM/CPU on a single node. Simple but limited and has no HA.

**Step 2 — Replication + Sentinel:**
```
Master  ← all writes
  ├── Replica 1  ← read scaling
  └── Replica 2  ← read scaling
Redis Sentinel → automatic failover if master dies
```

**Step 3 — Redis Cluster (horizontal write scaling):**
- 16384 hash slots distributed across N primary nodes
- Each node owns a slice of the keyspace
- Each primary has its own replica for HA
- Reads and writes both scale horizontally

**Lua script constraint in Cluster mode:**
All keys accessed in a Lua script must reside on the same node. Enforce with hash tags:
```
{product-A}:stock
{product-A}:idempotency:user-1
```
Redis hashes only the part inside `{}` — both keys land on the same slot.

**Step 4 — Stock sharding** to solve the hot-key problem on individual products (see Q5).

### Vietnamese

**Bước 1 — Vertical scaling:** tăng RAM/CPU cho single node. Đơn giản nhưng có giới hạn, không có HA.

**Bước 2 — Replication + Sentinel:** Master nhận writes, Replica phân tải reads. Sentinel tự động failover khi Master chết.

**Bước 3 — Redis Cluster:** 16384 hash slot phân tán qua N node. Cả reads lẫn writes scale ngang. Mỗi primary có replica riêng cho HA.

**Ràng buộc Lua script trong Cluster:** tất cả key trong Lua script phải nằm cùng node. Dùng hash tags `{product-A}` để đảm bảo co-location — Redis chỉ hash phần trong `{}`.

**Bước 4 — Stock sharding** để giải quyết hot-key problem cho từng sản phẩm.

---

## Q7: How does your system recover from failures?

### English

**1. Worker crash (most common):**
Worker reads message → writes to DB → crashes before XACK.
- Redis keeps the message in "delivered but unacknowledged" state
- On restart, worker calls `XAUTOCLAIM` to reclaim stale messages
- `ON CONFLICT DO NOTHING` makes the re-insert a safe no-op
- Rule: **only XACK after successful DB write**

**2. Redis crash:**
- AOF (Append-Only File) persistence enabled — every write is logged to disk
- On restart, Redis replays AOF and fully restores stock counts and stream messages
- No data loss for committed operations

**3. PostgreSQL down:**
- Worker INSERT fails → do not XACK → message stays in stream
- Retry with exponential backoff
- After exceeding retry limit → move to Dead Letter Queue (`orders:dlq` stream)
- Alert on-call engineer; replay from DLQ after fix

**4. Dead Letter Queue (DLQ):**
Prevents one poison message from blocking the entire consumer pipeline. Engineer investigates, fixes root cause, replays manually.

**5. API pod crash:**
- API is stateless → load balancer instantly routes to another pod
- Idempotency key still in Redis → client retry is safe

**6. Circuit Breaker:**
```
Redis errors > threshold → OPEN → return 503 immediately
After cooldown → HALF_OPEN → probe one request
Success → CLOSED | Failure → OPEN again
```
Prevents cascading failures by fast-failing instead of letting requests queue up and time out.

### Vietnamese

**1. Worker crash:** Message chưa XACK → Redis giữ lại → worker restart → `XAUTOCLAIM` lấy lại message → re-insert an toàn nhờ `ON CONFLICT DO NOTHING`. Quy tắc: **chỉ XACK sau khi ghi DB thành công**.

**2. Redis crash:** AOF persistence ghi mọi write xuống disk → restart → replay AOF → restore toàn bộ stock và stream. Không mất data.

**3. PostgreSQL down:** Worker retry với exponential backoff → quá retry limit → chuyển sang DLQ → alert engineer → replay thủ công sau khi fix.

**4. DLQ (Dead Letter Queue):** Ngăn 1 message lỗi block toàn bộ pipeline. Engineer investigate, fix, replay.

**5. API pod crash:** API stateless → load balancer route sang pod khác ngay. Client retry an toàn nhờ idempotency key còn trong Redis.

**6. Circuit Breaker:** Khi Redis error vượt threshold → OPEN → trả 503 ngay lập tức → không để request pile up → tránh cascading failure.

---

## Q8: How does your system handle backpressure?

### English

Backpressure occurs when the producer (API) generates work faster than the consumer (worker) can process it. Without backpressure handling, queues grow unbounded → OOM → system crash.

**Layer 1 — Rate Limiter (first gate):**
```
Per-user:  10 req/s  → 429 Too Many Requests
Global:    100k req/s → 429 at capacity
```
Caps incoming traffic before it enters the system. Protects every layer downstream.

**Layer 2 — Redis Stream MAXLEN:**
```python
await redis.xadd("orders", payload, maxlen=100_000, approximate=True)
```
Stream cannot grow beyond ~100k entries. `approximate=True` uses O(1) trimming. When the stream is full, the oldest entries are evicted — the API must not outpace the worker long-term.

**Layer 3 — Circuit Breaker:**
When Redis or PostgreSQL is struggling, the circuit opens and returns 503 immediately — stopping new load from compounding the problem.

**Layer 4 — Worker batch reads:**
```python
raw = await redis.xreadgroup(..., count=100)
```
Worker pulls a fixed batch per iteration — never overwhelms itself or the DB connection pool.

**Layer 5 — Horizontal consumer scaling:**
When one worker cannot keep up, add more instances to the same consumer group. Redis automatically distributes messages:
```
Stream: [m1, m2, m3, m4, m5, m6]
Worker-1: m1, m3, m5
Worker-2: m2, m4, m6
```

### Vietnamese

Backpressure xảy ra khi producer (API) tạo ra công việc nhanh hơn consumer (worker) xử lý. Không có backpressure → queue tăng vô hạn → hết RAM → crash.

**Layer 1 — Rate Limiter:** Giới hạn per-user và global request rate. Chặn traffic ngay từ đầu, bảo vệ mọi layer phía sau.

**Layer 2 — Redis Stream MAXLEN:** Stream không vượt ~100k entries. `approximate=True` → O(1) trimming. Khi stream đầy, entries cũ bị xóa — buộc API không được outpace worker về lâu dài.

**Layer 3 — Circuit Breaker:** Khi Redis/DB quá tải → circuit OPEN → 503 ngay lập tức → không thêm load vào hệ thống đang struggling.

**Layer 4 — Worker batch read:** Worker đọc `count=100` message mỗi lần → không overwhelm bản thân hay DB connection pool.

**Layer 5 — Horizontal consumer scaling:** Thêm worker instance vào cùng consumer group → Redis tự động phân tán message → throughput tăng tuyến tính.

---

## Summary Table

| Topic | Key Points |
|---|---|
| DB locking | Serialization, contention, timeout, deadlock, no horizontal scale |
| Lua atomicity | Single-threaded, no interrupt, no partial execution, eliminates race condition |
| Idempotency | SET NX (Redis) + ON CONFLICT DO NOTHING (PostgreSQL), two layers for two failure modes |
| Eventual consistency | API acks at enqueue, worker writes async, tradeoff: low latency vs brief inconsistency |
| Hot-key | One key → one node bottleneck, solved by stock sharding + local cache |
| Scale Redis | Replication → Sentinel → Cluster + hash tags for Lua co-location |
| Failure recovery | XACK after DB write, AOF, DLQ, circuit breaker, stateless API |
| Backpressure | Rate limiter, MAXLEN, circuit breaker, batch reads, horizontal consumer scaling |
