# Giải thích chi tiết `eventual_cache.py`

Đây là demo về **Eventual Consistency** - hệ thống distributed cache với 3 nodes có thể tạm thời không nhất quán, nhưng cuối cùng sẽ hội tụ.

---

## **Kiến trúc tổng quan**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Node A    │────▶│   Node B    │────▶│   Node C    │
│             │◀────│             │◀────│             │
│ data: {}    │     │ data: {}    │     │ data: {}    │
│ versions:{}│     │ versions:{}│     │ versions:{}│
└─────────────┘     └─────────────┘     └─────────────┘
     ▲                    ▲                    ▲
     │                    │                    │
   Write                Read                 Read
  (instant)           (may be              (may be
                       stale)               stale)
```

Mỗi node:
- Có **local data** riêng
- Tự replicate sang các peers **không đồng bộ** (async)
- Giải quyết conflicts bằng **Last-Write-Wins** (LWW)

---

## **1. Khởi tạo Node**

```python
class EventuallyConsistentCache:
    def __init__(self, node_id, peers=None):
        self.node_id = node_id           # ID của node này (vd: "Node-A")
        self.peers = peers or []         # Danh sách các nodes khác
        
        self.data = {}                   # Dữ liệu local: {key: {value, timestamp, version}}
        self.versions = defaultdict(     # Version vector cho từng key
            lambda: defaultdict(int)     # {key: {node_id: version_number}}
        )
        
        self.replication_queue = []      # Hàng đợi để replicate
        
        # Thread nền để replicate async
        self.replication_thread = threading.Thread(
            target=self._replicate_async,
            daemon=True
        )
        self.replication_thread.start()
```

**Ví dụ sau khi khởi tạo 3 nodes:**
```python
node_a = EventuallyConsistentCache("Node-A")
node_b = EventuallyConsistentCache("Node-B")
node_c = EventuallyConsistentCache("Node-C")

# Kết nối chúng làm peers
node_a.peers = [node_b, node_c]
node_b.peers = [node_a, node_c]
node_c.peers = [node_a, node_b]
```

---

## **2. Ghi dữ liệu (Write) - Local First**

```python
def write(self, key, value):
    # Bước 1: Ghi NGAY vào local (không đợi replicas)
    self.data[key] = {
        'value': value,
        'timestamp': time.time(),
        'version': self.versions[key][self.node_id]
    }
    
    # Bước 2: Tăng version của node này
    self.versions[key][self.node_id] += 1
    
    print(f"[{self.node_id}] WRITE {key}={value} (local)")
    
    # Bước 3: Thêm vào hàng đợi để replicate SAU (async)
    self.replication_queue.append({
        'key': key,
        'value': value,
        'timestamp': time.time(),
        'version': dict(self.versions[key])  # Snapshot của version vector
    })
    
    # Bước 4: Trả về NGAY LẬP TỨC (không đợi replication)
    return "OK"  # ← Low latency!
```

**Timeline của một write:**

```
T=0ms:   Client gọi node_a.write('user:123', {'name': 'Alice'})
         
T=0ms:   Node A ghi local ✓
         data = {'user:123': {'value': {...}, 'timestamp': 1000}}
         versions = {'user:123': {'Node-A': 1, 'Node-B': 0, 'Node-C': 0}}
         
T=0ms:   Trả về "OK" cho client ✓ (FAST!)
         
T=100ms: Background thread replicate tới Node B (async)
T=300ms: Background thread replicate tới Node C (async)
```

**Điểm quan trọng:**
- ✅ **Write cực nhanh** - chỉ ghi local, trả về ngay
- ✅ **High availability** - node có thể write ngay cả khi peers offline
- ❌ **Eventual consistency** - peers chưa có dữ liệu ngay lập tức

---

## **3. Đọc dữ liệu (Read) - May Be Stale**

```python
def read(self, key):
    # Đọc từ LOCAL node (có thể stale)
    if key in self.data:
        value = self.data[key]['value']
        print(f"[{self.node_id}] READ {key}={value} (local)")
        return value
    return None
```

**Ví dụ stale read:**

```python
# T=0ms: Write vào Node A
node_a.write('user:123', {'name': 'Alice', 'age': 30})
# Node A: có dữ liệu ✓
# Node B: CHƯA có (replication đang trong queue)
# Node C: CHƯA có

# T=10ms: Đọc từ các nodes khác nhau
node_a.read('user:123')  # → {'name': 'Alice', 'age': 30} ✓
node_b.read('user:123')  # → None (stale! chưa replicate tới)
node_c.read('user:123')  # → None (stale!)

# T=500ms: Sau khi replication hoàn tất
node_b.read('user:123')  # → {'name': 'Alice', 'age': 30} ✓ (now consistent!)
node_c.read('user:123')  # → {'name': 'Alice', 'age': 30} ✓
```

---

## **4. Replication không đồng bộ (Async)**

```python
def _replicate_async(self):
    """Background thread chạy liên tục"""
    while True:
        if self.replication_queue:
            # Lấy item từ queue
            item = self.replication_queue.pop(0)
            
            # Giả lập network delay (100-500ms)
            time.sleep(random.uniform(0.1, 0.5))
            
            # Gửi tới TẤT CẢ peers
            for peer in self.peers:
                try:
                    peer.receive_replication(item)
                except Exception as e:
                    # Peer offline? Không sao - thử lại sau
                    # (Eventually consistent - sẽ sync khi peer online lại)
                    print(f"Failed to replicate: {e}")
        
        time.sleep(0.1)  # Check queue mỗi 100ms
```

**Cơ chế hoạt động:**

```
Node A writes 'user:123'
│
├─ T=0ms:   Write local ✓
├─ T=0ms:   Add to replication_queue
│           queue = [{'key': 'user:123', 'value': {...}, ...}]
│
├─ T=100ms: Background thread picks from queue
│           Sleep 100-500ms (simulate network)
│           
├─ T=300ms: Send to Node B
│           peer.receive_replication(item)
│           
└─ T=500ms: Send to Node C
            peer.receive_replication(item)
```

---

## **5. Nhận Replication - Giải quyết Conflicts**

Đây là phần **QUAN TRỌNG NHẤT** - khi nhận dữ liệu replicated, có thể có **conflict**!

```python
def receive_replication(self, item):
    key = item['key']
    value = item['value']
    incoming_version = item['version']
    
    # Case 1: Key chưa tồn tại - không conflict
    if key not in self.data:
        self.data[key] = {
            'value': value,
            'timestamp': item['timestamp'],
            'version': incoming_version
        }
        print(f"[{self.node_id}] REPLICATED {key}={value}")
    
    # Case 2: Key đã tồn tại - CONFLICT!
    else:
        # So sánh timestamp (Last-Write-Wins)
        if item['timestamp'] > self.data[key]['timestamp']:
            # Incoming data mới hơn → chấp nhận
            print(f"[{self.node_id}] CONFLICT {key}: "
                  f"{self.data[key]['value']} -> {value} (LWW)")
            
            self.data[key] = {
                'value': value,
                'timestamp': item['timestamp'],
                'version': incoming_version
            }
    
    # Merge version vectors (quan trọng!)
    for node, version in incoming_version.items():
        self.versions[key][node] = max(
            self.versions[key][node],
            version
        )
```

**Ví dụ conflict:**

```python
# Concurrent writes trên 2 nodes khác nhau

T=0ms:  Node A writes: user:123 = {age: 30, timestamp: 1000}
T=50ms: Node B writes: user:123 = {age: 31, timestamp: 1050}  # Concurrent!

# Replication happens:
T=500ms: Node A nhận replication từ Node B
         Local:    {age: 30, timestamp: 1000}
         Incoming: {age: 31, timestamp: 1050}
         
         Compare timestamps: 1050 > 1000
         → Chấp nhận incoming (Last-Write-Wins)
         → Node A now has {age: 31}

T=600ms: Node B nhận replication từ Node A
         Local:    {age: 31, timestamp: 1050}
         Incoming: {age: 30, timestamp: 1000}
         
         Compare timestamps: 1000 < 1050
         → Từ chối incoming (keep local)
         → Node B still has {age: 31}

Result: Both converge to {age: 31} ✓ (Eventual consistency!)
```

---

## **6. Version Vectors - Theo dõi Causality**

Version vectors giúp detect conflicts tốt hơn timestamps.

```python
self.versions = {
    'user:123': {
        'Node-A': 2,  # Node A đã update key này 2 lần
        'Node-B': 1,  # Node B đã update 1 lần
        'Node-C': 0   # Node C chưa update
    }
}
```

**Ví dụ sử dụng:**

```python
# Initial state
versions['user:123'] = {'A': 0, 'B': 0, 'C': 0}

# Node A updates
node_a.write('user:123', 'value1')
versions['user:123'] = {'A': 1, 'B': 0, 'C': 0}  # A's version++

# Node B updates (concurrent!)
node_b.write('user:123', 'value2')
versions['user:123'] = {'A': 0, 'B': 1, 'C': 0}  # B's version++

# When merging:
# A's version: {'A': 1, 'B': 0, 'C': 0}
# B's version: {'A': 0, 'B': 1, 'C': 0}
# 
# Neither dominates! → Concurrent writes detected
# Use timestamp to break tie (Last-Write-Wins)
```

---

## **7. Demo Flow - Từng bước**

```python
def demo_eventual_consistency():
    # Tạo 3 nodes
    node_a = EventuallyConsistentCache("Node-A")
    node_b = EventuallyConsistentCache("Node-B")
    node_c = EventuallyConsistentCache("Node-C")
    
    # Kết nối peers
    node_a.peers = [node_b, node_c]
    node_b.peers = [node_a, node_c]
    node_c.peers = [node_a, node_b]
    
    # === STEP 1: Write to Node A ===
    print("1. Write 'user:123' to Node A")
    node_a.write('user:123', {'name': 'Alice', 'age': 30})
    # Output: [Node-A] WRITE user:123={'name': 'Alice', 'age': 30} (local)
    
    # === STEP 2: Immediate read (stale!) ===
    print("\n2. Immediately read from all nodes:")
    print(f"   Node A: {node_a.read('user:123')}")  # ✓ Has data
    print(f"   Node B: {node_b.read('user:123')}")  # ✗ None (stale)
    print(f"   Node C: {node_c.read('user:123')}")  # ✗ None (stale)
    
    # === STEP 3: Wait for replication ===
    print("\n3. Wait 1 second for replication...")
    time.sleep(1)
    # Background thread đã replicate tới B và C
    
    # === STEP 4: Read again (consistent now!) ===
    print("\n4. Read after replication:")
    print(f"   Node A: {node_a.read('user:123')}")  # ✓ Has data
    print(f"   Node B: {node_b.read('user:123')}")  # ✓ Has data (replicated!)
    print(f"   Node C: {node_c.read('user:123')}")  # ✓ Has data (replicated!)
    
    # === STEP 5: Concurrent writes (conflict!) ===
    print("\n5. Concurrent writes on different nodes:")
    node_a.write('user:123', {'name': 'Alice', 'age': 31})  # T=1000
    time.sleep(0.05)
    node_b.write('user:123', {'name': 'Alice', 'age': 32})  # T=1050 (later)
    
    # === STEP 6: Wait for conflict resolution ===
    print("\n6. Wait for conflict resolution...")
    time.sleep(1)
    
    # === STEP 7: All converged (Last-Write-Wins) ===
    print("\n7. Final state (after convergence):")
    print(f"   Node A: {node_a.read('user:123')}")  # age: 32
    print(f"   Node B: {node_b.read('user:123')}")  # age: 32
    print(f"   Node C: {node_c.read('user:123')}")  # age: 32
    print("\n   All nodes converged! (Eventual consistency)")
```

---

## **Tóm tắt Timeline đầy đủ**

```
T=0ms:    node_a.write('user:123', {age: 30})
          ├─ Node A: {age: 30} ✓
          ├─ Node B: None (chưa replicate)
          └─ Node C: None (chưa replicate)

T=100ms:  Replication thread hoạt động
          └─ Queued for replication

T=300ms:  Replicated to Node B
          ├─ Node A: {age: 30} ✓
          ├─ Node B: {age: 30} ✓ (vừa nhận)
          └─ Node C: None

T=500ms:  Replicated to Node C
          ├─ Node A: {age: 30} ✓
          ├─ Node B: {age: 30} ✓
          └─ Node C: {age: 30} ✓ (EVENTUAL CONSISTENCY đạt được!)

T=1000ms: Concurrent writes
          node_a.write({age: 31})  @ timestamp 1000
          node_b.write({age: 32})  @ timestamp 1050

T=1500ms: After conflict resolution (LWW)
          ├─ Node A: {age: 32} ✓ (accepted B's write - newer timestamp)
          ├─ Node B: {age: 32} ✓ (kept own write)
          └─ Node C: {age: 32} ✓ (merged both, took newer)
          
          ALL CONVERGED! (Eventually consistent)
```

---

## **Các khái niệm chính**

| Khái niệm | Giải thích | Trong code |
|-----------|-----------|-----------|
| **Eventual Consistency** | Cuối cùng tất cả nodes sẽ có cùng data | Sau vài trăm ms, tất cả nodes đồng bộ |
| **Async Replication** | Replicate không đợi, chạy background | `_replicate_async()` thread |
| **Stale Reads** | Đọc có thể trả về data cũ | Node B/C trả về `None` ngay sau write |
| **Last-Write-Wins** | Conflict resolution: giữ write mới nhất | So sánh `timestamp` |
| **Version Vectors** | Theo dõi causality của updates | `self.versions[key][node_id]` |
| **High Availability** | Vẫn write được khi peers offline | Write local ngay, không cần peers |
| **Low Latency** | Write trả về ngay, không đợi | `return "OK"` immediately |

---

## **So sánh với Strong Consistency**

| Aspect | Eventual Consistency (code này) | Strong Consistency |
|--------|-------------------------------|-------------------|
| **Write speed** | Instant (local only) | Slow (wait for all replicas) |
| **Read accuracy** | May be stale | Always latest |
| **Availability** | High (works offline) | Lower (needs quorum) |
| **Conflict** | Possible (LWW resolves) | Prevented (locks) |
| **Use case** | Caching, social media | Banking, inventory |

Hiểu rồi chứ? Có câu hỏi gì về code không? 😊