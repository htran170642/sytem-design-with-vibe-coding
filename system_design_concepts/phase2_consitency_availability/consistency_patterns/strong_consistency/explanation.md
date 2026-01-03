# Giải thích chi tiết `strong_consistency_lock.py`

Đây là demo về **Strong Consistency** sử dụng giao thức **Two-Phase Commit (2PC)** - đảm bảo tất cả nodes hoặc cùng commit, hoặc cùng abort (không có trạng thái nửa vời).

---

## **Kiến trúc tổng quan**

```
                    ┌─────────────────┐
                    │  Coordinator    │
                    │  (Điều phối)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │  DB-1   │    │  DB-2   │    │  DB-3   │
        │(Node)   │    │(Node)   │    │(Node)   │
        └─────────┘    └─────────┘    └─────────┘

PHASE 1: Coordinator hỏi TẤT CẢ: "Có thể commit không?"
         → Mỗi node vote YES hoặc NO

PHASE 2: Nếu TẤT CẢ vote YES → Coordinator ra lệnh COMMIT
         Nếu có BẤT KỲ node vote NO → Coordinator ra lệnh ABORT
```

**Đặc điểm:**
- ✅ **Atomic**: Tất cả commit hoặc tất cả abort (không có trạng thái giữa chừng)
- ✅ **Consistent**: Tất cả nodes luôn có cùng state
- ❌ **Blocking**: Nếu 1 node fail → toàn bộ transaction fail
- ❌ **High latency**: Phải đợi tất cả nodes respond

---

## **1. DatabaseNode - Mỗi node trong distributed system**

```python
class DatabaseNode:
    """
    Mô phỏng một database node tham gia vào 2PC.
    Giống như một replica trong distributed database.
    """
    
    def __init__(self, node_id, fail_probability=0.0):
        self.node_id = node_id                    # Tên node: "DB-1", "DB-2"...
        self.fail_probability = fail_probability  # Xác suất fail (để test)
        self.prepared_transactions = {}           # Các transaction đã PREPARE
        self.lock = threading.Lock()              # Thread-safe
```

**Prepared transactions** là gì?
```python
# Khi node nhận PREPARE, nó "chuẩn bị" transaction:
self.prepared_transactions = {
    'txn_1': 'INSERT user_id=123',  # Sẵn sàng commit operation này
    'txn_2': 'UPDATE balance=5000',  # Sẵn sàng commit operation này
}
# Chưa thực thi, chỉ "khóa" resources và sẵn sàng
```

---

## **2. PHASE 1: PREPARE (Vote)**

```python
def prepare(self, transaction_id, operation):
    """
    Phase 1 của 2PC: Node được hỏi "Bạn có thể commit transaction này không?"
    
    Node phải kiểm tra:
    - Có đủ locks không?
    - Có đủ disk space không?
    - Constraints có vi phạm không?
    - Có thể rollback không (nếu cần)?
    
    Returns: "YES" hoặc "NO"
    """
    
    # Giả lập node fail ngẫu nhiên (để test failure scenarios)
    if random.random() < self.fail_probability:
        print(f"  [{self.node_id}] ❌ VOTE-NO (simulated failure)")
        return "NO"
    
    with self.lock:
        # Trong thực tế, ở đây sẽ:
        # 1. Kiểm tra constraints
        # 2. Lấy locks cần thiết
        # 3. Write to transaction log (để có thể rollback)
        # 4. Verify có thể commit
        
        # Lưu transaction vào "prepared" state
        self.prepared_transactions[transaction_id] = operation
        
        print(f"  [{self.node_id}] ✓ VOTE-YES (prepared)")
        return "YES"
```

**Ví dụ thực tế:**

```python
# Transfer $100 từ Account A sang Account B
# Operation cho DB-1: "DEBIT account_A $100"
# Operation cho DB-2: "CREDIT account_B $100"

db1.prepare(txn_id=1, operation="DEBIT account_A $100")
# DB-1 kiểm tra:
#   - Account A có tồn tại? ✓
#   - Account A có đủ $100? ✓
#   - Có lock được account A? ✓
#   → Vote YES

db2.prepare(txn_id=1, operation="CREDIT account_B $100")
# DB-2 kiểm tra:
#   - Account B có tồn tại? ✓
#   - Có lock được account B? ✓
#   → Vote YES
```

**Trường hợp vote NO:**

```python
db1.prepare(txn_id=2, operation="DEBIT account_A $1000")
# DB-1 kiểm tra:
#   - Account A chỉ có $500 (không đủ $1000!)
#   → Vote NO ❌

# Kết quả: Toàn bộ transaction sẽ bị ABORT
```

---

## **3. PHASE 2a: COMMIT (Thành công)**

```python
def commit(self, transaction_id):
    """
    Phase 2 (success path): Coordinator ra lệnh COMMIT.
    Node thực sự thực thi operation.
    """
    with self.lock:
        if transaction_id in self.prepared_transactions:
            operation = self.prepared_transactions[transaction_id]
            
            # Thực thi operation (thực sự ghi vào database)
            # Trong thực tế: apply changes, release locks
            print(f"  [{self.node_id}] ✓ COMMITTED: {operation}")
            
            # Xóa khỏi prepared state
            del self.prepared_transactions[transaction_id]
            return True
        return False
```

**Timeline commit:**

```
T=0ms:   Coordinator: "DB-1, commit txn_1"
T=1ms:   DB-1 executes: DEBIT account_A $100
         Database now has: account_A = $900 (was $1000)
         Release locks
         Return success

T=5ms:   Coordinator: "DB-2, commit txn_1"
T=6ms:   DB-2 executes: CREDIT account_B $100
         Database now has: account_B = $600 (was $500)
         Release locks
         Return success

Result: BOTH databases updated ✓ (Strong consistency!)
```

---

## **4. PHASE 2b: ABORT (Thất bại)**

```python
def abort(self, transaction_id):
    """
    Phase 2 (failure path): Coordinator ra lệnh ABORT.
    Node hủy bỏ prepared transaction.
    """
    with self.lock:
        if transaction_id in self.prepared_transactions:
            print(f"  [{self.node_id}] ✗ ABORTED")
            
            # Rollback changes (nếu có)
            # Release locks
            # Discard prepared transaction
            del self.prepared_transactions[transaction_id]
            return True
        return False
```

**Timeline abort:**

```
T=0ms:   DB-1 votes YES (prepared)
T=5ms:   DB-2 votes NO (cannot prepare - account locked by other txn)

T=10ms:  Coordinator nhận votes: [YES, NO]
         Decision: ABORT (vì có NO)

T=15ms:  Coordinator: "DB-1, abort txn_1"
T=16ms:  DB-1 rollback: Discard prepared changes
         Release locks
         Database unchanged (account_A still $1000)

T=20ms:  Coordinator: "DB-2, abort txn_1"
T=21ms:  DB-2: Nothing to abort (never prepared)

Result: BOTH databases unchanged ✓ (Strong consistency - no partial commit!)
```

---

## **5. TwoPhaseCommitCoordinator - Điều phối viên**

```python
class TwoPhaseCommitCoordinator:
    """
    Coordinator chịu trách nhiệm điều phối 2PC protocol.
    Quyết định commit hay abort dựa trên votes.
    """
    
    def __init__(self, nodes):
        self.nodes = nodes              # Danh sách các DB nodes
        self.transaction_id = 0         # Counter cho transaction IDs
```

---

## **6. Execute Transaction - Toàn bộ flow 2PC**

```python
def execute_transaction(self, operations):
    """
    Thực thi distributed transaction với strong consistency.
    TẤT CẢ nodes commit, hoặc TẤT CẢ abort (atomic).
    
    Args:
        operations: List of operations cho mỗi node
                   ['INSERT user_id=123', 'INSERT profile_id=123', ...]
    """
    
    # Tạo transaction ID mới
    self.transaction_id += 1
    tid = self.transaction_id
    
    print(f"\n{'='*60}")
    print(f"Transaction {tid}: {operations}")
    print(f"{'='*60}")
```

### **PHASE 1: PREPARE (Hỏi tất cả nodes)**

```python
    # ====== PHASE 1: PREPARE ======
    print(f"\n[PHASE 1] Coordinator sends PREPARE to all nodes")
    prepare_votes = []
    
    # Gửi PREPARE request tới TẤT CẢ nodes
    for i, node in enumerate(self.nodes):
        vote = node.prepare(tid, operations[i])
        prepare_votes.append(vote)
        time.sleep(0.1)  # Simulate network latency
    
    print(f"\n[PHASE 1] Votes received: {prepare_votes}")
```

**Ví dụ PHASE 1:**

```
Transaction 1: ['INSERT user_id=123', 'INSERT profile_id=123', 'INSERT perm_id=123']

[PHASE 1] Coordinator sends PREPARE to all nodes
  [DB-1] ✓ VOTE-YES (prepared)
  [DB-2] ✓ VOTE-YES (prepared)
  [DB-3] ✓ VOTE-YES (prepared)

[PHASE 1] Votes received: ['YES', 'YES', 'YES']
```

### **Decision Logic: ALL or NOTHING**

```python
    # Quyết định dựa trên votes
    if all(vote == "YES" for vote in prepare_votes):
        # ====== PHASE 2: COMMIT ======
        print(f"\n[PHASE 2] All voted YES → Coordinator sends COMMIT")
        
        # Ra lệnh COMMIT cho TẤT CẢ nodes
        for node in self.nodes:
            node.commit(tid)
            time.sleep(0.1)
        
        print(f"\n✅ Transaction {tid} COMMITTED on all nodes")
        print("   Strong consistency maintained: all nodes have same state")
        return "COMMITTED"
```

**Ví dụ COMMIT path:**

```
[PHASE 2] All voted YES → Coordinator sends COMMIT
  [DB-1] ✓ COMMITTED: INSERT user_id=123
  [DB-2] ✓ COMMITTED: INSERT profile_id=123
  [DB-3] ✓ COMMITTED: INSERT perm_id=123

✅ Transaction 1 COMMITTED on all nodes
   Strong consistency maintained: all nodes have same state
```

### **ABORT path:**

```python
    else:
        # ====== PHASE 2: ABORT ======
        print(f"\n[PHASE 2] At least one voted NO → Coordinator sends ABORT")
        
        # Ra lệnh ABORT cho TẤT CẢ nodes
        for node in self.nodes:
            node.abort(tid)
            time.sleep(0.1)
        
        print(f"\n❌ Transaction {tid} ABORTED on all nodes")
        print("   Strong consistency maintained: no partial commits")
        return "ABORTED"
```

**Ví dụ ABORT path:**

```
Transaction 2: ['INSERT user_id=456', 'INSERT profile_id=456', 'INSERT perm_id=456']

[PHASE 1] Coordinator sends PREPARE to all nodes
  [DB-1] ✓ VOTE-YES (prepared)
  [DB-2] ❌ VOTE-NO (simulated failure)  ← Một node fail!
  [DB-3] ✓ VOTE-YES (prepared)

[PHASE 1] Votes received: ['YES', 'NO', 'YES']

[PHASE 2] At least one voted NO → Coordinator sends ABORT
  [DB-1] ✗ ABORTED
  [DB-2] ✗ ABORTED
  [DB-3] ✗ ABORTED

❌ Transaction 2 ABORTED on all nodes
   Strong consistency maintained: no partial commits
```

---

## **7. Flow Chart đầy đủ**

### **Success Case (All YES):**

```
Coordinator                 DB-1              DB-2              DB-3
    │                        │                 │                 │
    │─── PREPARE txn_1 ─────▶│                 │                 │
    │                        │ Check resources │                 │
    │                        │ Acquire locks   │                 │
    │◀──── VOTE-YES ─────────│                 │                 │
    │                        │                 │                 │
    │─── PREPARE txn_1 ──────┼────────────────▶│                 │
    │                        │                 │ Check resources │
    │                        │                 │ Acquire locks   │
    │◀──── VOTE-YES ─────────┼─────────────────│                 │
    │                        │                 │                 │
    │─── PREPARE txn_1 ──────┼─────────────────┼────────────────▶│
    │                        │                 │                 │ Check resources
    │                        │                 │                 │ Acquire locks
    │◀──── VOTE-YES ─────────┼─────────────────┼─────────────────│
    │                        │                 │                 │
    │ Decision: ALL YES      │                 │                 │
    │ → COMMIT               │                 │                 │
    │                        │                 │                 │
    │──── COMMIT txn_1 ──────▶│                 │                 │
    │                        │ Apply changes   │                 │
    │                        │ Release locks   │                 │
    │◀──── ACK ──────────────│                 │                 │
    │                        │                 │                 │
    │──── COMMIT txn_1 ───────┼────────────────▶│                 │
    │                        │                 │ Apply changes   │
    │                        │                 │ Release locks   │
    │◀──── ACK ───────────────┼─────────────────│                 │
    │                        │                 │                 │
    │──── COMMIT txn_1 ───────┼─────────────────┼────────────────▶│
    │                        │                 │                 │ Apply changes
    │                        │                 │                 │ Release locks
    │◀──── ACK ───────────────┼─────────────────┼─────────────────│
    │                        │                 │                 │
    ✓ All committed          ✓ Committed       ✓ Committed       ✓ Committed
```

### **Failure Case (At least one NO):**

```
Coordinator                 DB-1              DB-2              DB-3
    │                        │                 │                 │
    │─── PREPARE txn_2 ─────▶│                 │                 │
    │◀──── VOTE-YES ─────────│                 │                 │
    │                        │                 │                 │
    │─── PREPARE txn_2 ──────┼────────────────▶│                 │
    │◀──── VOTE-NO ──────────┼─────────────────│ (Failed!)       │
    │                        │                 │                 │
    │─── PREPARE txn_2 ──────┼─────────────────┼────────────────▶│
    │◀──── VOTE-YES ─────────┼─────────────────┼─────────────────│
    │                        │                 │                 │
    │ Decision: ONE NO       │                 │                 │
    │ → ABORT                │                 │                 │
    │                        │                 │                 │
    │──── ABORT txn_2 ───────▶│                 │                 │
    │                        │ Rollback        │                 │
    │                        │ Release locks   │                 │
    │◀──── ACK ──────────────│                 │                 │
    │                        │                 │                 │
    │──── ABORT txn_2 ────────┼────────────────▶│                 │
    │                        │                 │ Rollback        │
    │◀──── ACK ───────────────┼─────────────────│                 │
    │                        │                 │                 │
    │──── ABORT txn_2 ────────┼─────────────────┼────────────────▶│
    │                        │                 │                 │ Rollback
    │◀──── ACK ───────────────┼─────────────────┼─────────────────│
    │                        │                 │                 │
    ✗ All aborted            ✗ Aborted         ✗ Aborted         ✗ Aborted
```

---

## **8. Demo Function - Hai Scenarios**

### **Scenario 1: All nodes healthy (SUCCESS)**

```python
def demo_strong_consistency():
    # Tạo 3 database nodes (không có failure)
    db1 = DatabaseNode("DB-1")
    db2 = DatabaseNode("DB-2")
    db3 = DatabaseNode("DB-3")
    
    coordinator = TwoPhaseCommitCoordinator([db1, db2, db3])
    
    print("SCENARIO 1: All nodes healthy")
    
    coordinator.execute_transaction([
        "INSERT user_id=123 INTO users",
        "INSERT user_id=123 INTO profiles", 
        "INSERT user_id=123 INTO permissions"
    ])
```

**Output:**

```
============================================================
Transaction 1: ['INSERT user_id=123 INTO users', 'INSERT user_id=123 INTO profiles', 'INSERT user_id=123 INTO permissions']
============================================================

[PHASE 1] Coordinator sends PREPARE to all nodes
  [DB-1] ✓ VOTE-YES (prepared)
  [DB-2] ✓ VOTE-YES (prepared)
  [DB-3] ✓ VOTE-YES (prepared)

[PHASE 1] Votes received: ['YES', 'YES', 'YES']

[PHASE 2] All voted YES → Coordinator sends COMMIT
  [DB-1] ✓ COMMITTED: INSERT user_id=123 INTO users
  [DB-2] ✓ COMMITTED: INSERT user_id=123 INTO profiles
  [DB-3] ✓ COMMITTED: INSERT user_id=123 INTO permissions

✅ Transaction 1 COMMITTED on all nodes
   Strong consistency maintained: all nodes have same state
```

### **Scenario 2: One node fails (ALL ABORT)**

```python
    # Make DB-2 fail 100% of the time
    db2.fail_probability = 1.0
    
    print("SCENARIO 2: One node fails during PREPARE")
    
    coordinator.execute_transaction([
        "INSERT user_id=456 INTO users",
        "INSERT user_id=456 INTO profiles",
        "INSERT user_id=456 INTO permissions"
    ])
```

**Output:**

```
============================================================
Transaction 2: ['INSERT user_id=456 INTO users', 'INSERT user_id=456 INTO profiles', 'INSERT user_id=456 INTO permissions']
============================================================

[PHASE 1] Coordinator sends PREPARE to all nodes
  [DB-1] ✓ VOTE-YES (prepared)
  [DB-2] ❌ VOTE-NO (simulated failure)
  [DB-3] ✓ VOTE-YES (prepared)

[PHASE 1] Votes received: ['YES', 'NO', 'YES']

[PHASE 2] At least one voted NO → Coordinator sends ABORT
  [DB-1] ✗ ABORTED
  [DB-2] ✗ ABORTED
  [DB-3] ✗ ABORTED

❌ Transaction 2 ABORTED on all nodes
   Strong consistency maintained: no partial commits
```

---

## **9. Timeline chi tiết của một transaction**

```
T=0ms     Coordinator: Bắt đầu transaction 1
          Operations: [op1, op2, op3] cho 3 nodes

T=1ms     [PHASE 1 START]
          Coordinator → DB-1: "PREPARE op1"

T=50ms    DB-1 kiểm tra:
          - Locks available? ✓
          - Constraints OK? ✓
          - Resources sufficient? ✓
          DB-1 → Coordinator: "VOTE-YES"

T=100ms   Coordinator → DB-2: "PREPARE op2"

T=150ms   DB-2 kiểm tra:
          - Locks available? ✓
          - Constraints OK? ✓
          - Resources sufficient? ✓
          DB-2 → Coordinator: "VOTE-YES"

T=200ms   Coordinator → DB-3: "PREPARE op3"

T=250ms   DB-3 kiểm tra:
          - Locks available? ✓
          - Constraints OK? ✓
          - Resources sufficient? ✓
          DB-3 → Coordinator: "VOTE-YES"

T=300ms   [PHASE 1 COMPLETE]
          Coordinator has all votes: [YES, YES, YES]
          Decision: COMMIT ✓

T=301ms   [PHASE 2 START]
          Coordinator → DB-1: "COMMIT"

T=350ms   DB-1 executes op1
          DB-1 releases locks
          DB-1 → Coordinator: "ACK"

T=400ms   Coordinator → DB-2: "COMMIT"

T=450ms   DB-2 executes op2
          DB-2 releases locks
          DB-2 → Coordinator: "ACK"

T=500ms   Coordinator → DB-3: "COMMIT"

T=550ms   DB-3 executes op3
          DB-3 releases locks
          DB-3 → Coordinator: "ACK"

T=600ms   [PHASE 2 COMPLETE]
          Transaction COMMITTED on all nodes ✓
          
Total latency: 600ms (vs ~10ms for eventual consistency!)
```

---

## **10. So sánh Strong vs Eventual Consistency**

| Aspect | Strong (2PC) | Eventual |
|--------|-------------|----------|
| **Write latency** | 600ms (wait for all) | 1ms (local only) |
| **Consistency** | Immediate, always correct | Eventually correct |
| **Availability** | Lower (1 node down = fail) | Higher (works offline) |
| **Failure handling** | Abort all if 1 fails | Continue with failures |
| **Conflict** | Prevented by locks | Resolved by LWW/vectors |
| **Use case** | Banking, inventory | Social media, caching |

### **Ví dụ thực tế:**

**Banking (cần Strong):**
```python
# Transfer $100: Account A → Account B
# Phải đảm bảo:
# - Account A giảm $100
# - Account B tăng $100
# - HOẶC cả hai không thay đổi

# 2PC ensures: 
# - Both happen, or neither happens (atomic)
# - No possibility of money lost or duplicated
```

**Social Media (dùng Eventual OK):**
```python
# User posts "Hello world"
# Eventual consistency:
# - US users see post immediately
# - EU users see it after 100ms
# - Asia users see it after 300ms
# - Eventually all see it ✓

# Acceptable: Feed not mission-critical
# Better: Fast posting experience
```

---

## **11. Vấn đề của 2PC - Blocking Protocol**

**Coordinator crashes sau PREPARE:**

```
T=0ms:   Coordinator sends PREPARE to all
T=100ms: All nodes vote YES (and LOCK resources)
T=150ms: COORDINATOR CRASHES! 💥

Nodes are stuck:
- DB-1: Has locks, waiting for COMMIT/ABORT
- DB-2: Has locks, waiting for COMMIT/ABORT
- DB-3: Has locks, waiting for COMMIT/ABORT

Resources LOCKED indefinitely!
→ This is why 2PC is called "blocking protocol"
```

**Giải pháp:** Sử dụng 3PC (Three-Phase Commit) hoặc Paxos/Raft.

---

## **Tóm tắt Key Points**

1. **Two-Phase Commit** = PREPARE + COMMIT/ABORT
2. **Atomic**: All-or-nothing (tất cả commit hoặc tất cả abort)
3. **Strong Consistency**: Tất cả nodes luôn có cùng state
4. **Trade-off**: High latency, low availability
5. **Use when**: Correctness > Speed (banking, inventory, bookings)

Hiểu rồi chứ? Có câu hỏi gì về 2PC không? 😊