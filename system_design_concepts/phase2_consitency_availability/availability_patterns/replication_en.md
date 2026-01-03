# Part 2: Availability Patterns - Explanation Only

---

## **Replication (Explanation)**

**Definition:** Copying data across multiple servers to provide redundancy, fault tolerance, and improved read performance.

---

## **1. Master-Slave Replication (Primary-Replica)**

### **Architecture Overview**

```
                    ┌──────────────┐
           Writes   │    Master    │   Reads
        ────────────►│  (Primary)   │◄────────
                    └───────┬──────┘
                            │
                   Replication (one-way)
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  Slave 1 │      │  Slave 2 │      │  Slave 3 │
    │ (Replica)│      │ (Replica)│      │ (Replica)│
    └──────────┘      └──────────┘      └──────────┘
         ▲                 ▲                 ▲
         │                 │                 │
       Reads             Reads             Reads
```

### **How It Works**

**Write Path:**
1. Client sends write request
2. **Only Master** can accept writes
3. Master writes to its local storage
4. Master replicates to **all Slaves** (one direction)
5. Return success to client (timing depends on replication mode)

**Read Path:**
1. Client sends read request
2. Can read from **Master OR any Slave**
3. Load balancer distributes read traffic across all nodes
4. Reduces load on Master (read scaling)

### **Replication Modes**

#### **Asynchronous Replication (Eventual Consistency)**

**Timeline:**
```
T=0ms:   Client writes to Master
T=1ms:   Master saves locally
T=2ms:   Master returns "Success" to client ← FAST!
T=50ms:  Master replicates to Slave-1 (background)
T=150ms: Master replicates to Slave-2
T=300ms: Master replicates to Slave-3

During T=2ms to T=300ms: Slaves have STALE data
After T=300ms: All consistent (eventually)
```

**Characteristics:**
- ✅ **Fast writes** (~1-2ms) - doesn't wait for slaves
- ✅ **High availability** - works even if slaves are down
- ❌ **Eventual consistency** - slaves lag behind master
- ❌ **Data loss risk** - if master crashes before replication completes

**Example Scenario:**
```
User posts comment on Facebook:
T=0ms:   Write to Master in US datacenter
T=1ms:   User sees "Comment posted!" ✓
T=100ms: Replicate to EU datacenter
T=300ms: Replicate to Asia datacenter

User in US: Sees comment immediately
User in EU: Sees comment after 100ms
User in Asia: Sees comment after 300ms

Acceptable: Social media feed doesn't need instant global consistency
```

#### **Synchronous Replication (Strong Consistency)**

**Timeline:**
```
T=0ms:   Client writes to Master
T=1ms:   Master saves locally
T=2ms:   Master sends to Slave-1 → waits for ACK
T=50ms:  Slave-1 ACK received
T=51ms:  Master sends to Slave-2 → waits for ACK
T=150ms: Slave-2 ACK received
T=151ms: Master sends to Slave-3 → waits for ACK
T=300ms: Slave-3 ACK received
T=301ms: Master returns "Success" to client ← SLOW but SAFE

All slaves have data BEFORE client is notified
```

**Characteristics:**
- ❌ **Slow writes** (~100-300ms) - waits for all slaves
- ✅ **Strong consistency** - all nodes immediately consistent
- ✅ **No data loss** - slaves have data before write returns
- ❌ **Lower availability** - write fails if any slave is down

**Example Scenario:**
```
Bank account transfer:
User transfers $1000 from Account A to Account B

T=0ms:   Write to Master (debit $1000 from A)
T=1ms:   Master saves
T=100ms: Wait for ALL slaves to replicate
T=101ms: ALL slaves confirmed they have the transaction
T=102ms: Return success to user

If user immediately checks balance on ANY ATM (any server):
→ All show correct balance
→ No possibility of seeing old balance
```

#### **Semi-Synchronous Replication (Hybrid)**

**How it works:**
- Wait for **at least ONE** slave to acknowledge (not all)
- Other slaves replicate asynchronously

**Timeline:**
```
T=0ms:   Write to Master
T=1ms:   Master saves locally
T=2ms:   Send to all 3 slaves
T=50ms:  Slave-1 ACK (first to respond)
T=51ms:  Master returns "Success" ← Faster than full sync!
T=150ms: Slave-2 ACK (background)
T=300ms: Slave-3 ACK (background)
```

**Characteristics:**
- ✅ **Balanced latency** (~50ms) - only wait for one slave
- ✅ **Good durability** - at least 2 copies (master + 1 slave)
- ⚠️ **Hybrid consistency** - better than async, not as strong as sync
- ✅ **Better availability** - tolerates some slave failures

**Use case:** MySQL's semi-sync replication, PostgreSQL with quorum commits

---

### **Read Scaling Benefits**

**Scenario: Web application with 90% reads, 10% writes**

**Without Slaves (Master only):**
```
Master handles:
- 1,000 writes/sec
- 9,000 reads/sec
Total: 10,000 requests/sec

Master CPU: 100% (bottleneck!)
```

**With 3 Slaves:**
```
Master handles:
- 1,000 writes/sec
- 2,250 reads/sec (25% of read load)
Total: 3,250 requests/sec (Master CPU: 32%)

Each Slave handles:
- 2,250 reads/sec
Slave CPU: 22% each

Total system capacity: 
- Same 1,000 writes/sec (master bottleneck)
- 9,000 reads/sec distributed
- Room to grow!
```

**Scaling pattern:**
```
1 Master + 0 Slaves:  10,000 reads/sec max
1 Master + 3 Slaves:  40,000 reads/sec (4× improvement)
1 Master + 9 Slaves: 100,000 reads/sec (10× improvement)
```

### **Write Bottleneck**

**Problem:**
```
All writes must go through Master
Master can handle: 10,000 writes/sec

What if we need 50,000 writes/sec?
→ Adding slaves doesn't help (they only handle reads)
→ Master is the bottleneck

Solutions:
1. Vertical scaling: Bigger master server (limited, expensive)
2. Sharding: Split data across multiple master-slave clusters
3. Master-Master: Multiple masters (complex)
```

---

### **Replication Lag**

**What is it:**
The time delay between when data is written to master and when it appears on slaves.

**Typical lag:**
```
Same datacenter:    10-100ms
Cross-region:       100-500ms
Transcontinental:   200-1000ms
```

**Problems caused by lag:**

**1. Read-Your-Writes Consistency Violation:**
```
User posts a tweet:
T=0ms:   Write to Master (US-East)
T=1ms:   User redirected to profile page
T=2ms:   Profile page reads from Slave (US-West)
         Slave hasn't received replication yet!
         User: "Where's my tweet?!" ❌
```

**Solution:**
```
After write, temporarily read from Master for that user:
T=0ms:   Write to Master
T=1ms:   Store session: "read_from_master_until = T + 5 seconds"
T=2ms:   Profile page checks session → reads from Master
T=2ms:   User sees their tweet ✓
T=5s:    Session expires → can read from Slave again
```

**2. Moving Backwards in Time:**
```
User refreshes page twice:
Refresh 1: Load balanced to Slave-A (replication lag: 100ms)
           Sees 100 tweets

Refresh 2: Load balanced to Slave-B (replication lag: 500ms)
           Sees 95 tweets (older state!)
           
User: "Did I lose 5 tweets?!" ❌
```

**Solution:**
```
Monotonic reads: Stick user to same slave
- Use sticky sessions (cookie)
- Or: Include timestamp in reads, only show data newer than last seen
```

**3. Causality Violations:**
```
Alice posts: "Bob is the winner!"
Bob replies: "Thanks Alice!"

Timeline:
T=0:   Alice's post written to Master
T=1:   Master replicates to Slave-A
T=2:   Bob reads from Slave-A, sees Alice's post
T=3:   Bob's reply written to Master
T=4:   Master replicates to Slave-B (but Alice's post not yet there!)

User reading from Slave-B sees:
  Bob: "Thanks Alice!"
  (Where's Alice's post?!) ❌
```

**Solution:**
```
Consistent prefix reads: Ensure related writes appear in order
- Use version vectors
- Or: Read from Master for dependent reads
```

---

### **Slave Promotion (Failover)**

**When Master fails, promote a Slave to become new Master:**

**Process:**
```
1. Detect Master failure (30-60 seconds)
   - Heartbeat timeout
   - Multiple confirmation checks

2. Choose which Slave to promote (10-20 seconds)
   - Prefer slave with least replication lag
   - Check data consistency
   
3. Promote Slave (20-40 seconds)
   - Stop replication on chosen slave
   - Make it writable (change configuration)
   - Update DNS/load balancer
   
4. Update other Slaves (10-30 seconds)
   - Point them to new Master
   - Start replicating from new Master
   
Total: 70-150 seconds downtime
```

**Data Loss Risk:**

**Scenario:**
```
T=0:     Master receives write: "order_id=999"
T=1:     Master saves locally
T=2:     Master starts async replication
T=3:     Master CRASHES! 💥
         (Before replication completes)

T=60:    Slave promoted to new Master
         Slave doesn't have order_id=999
         
Result: Order lost! ❌
```

**How to minimize:**
```
1. Use synchronous replication (wait for at least 1 slave)
2. Use semi-sync (balance speed vs safety)
3. Frequent WAL (Write-Ahead Log) shipping
4. Have monitoring to detect and alert on lag
```

---

## **2. Master-Master Replication (Multi-Master)**

### **Architecture Overview**

```
           ┌──────────────┐
    Writes │   Master A   │ Writes
 ─────────►│              │◄─────────
    Reads  │              │  Reads
           └──────┬───────┘
                  │
         Bidirectional Sync
         (Both directions)
                  │
           ┌──────┴───────┐
    Writes │   Master B   │ Writes
 ─────────►│              │◄─────────
    Reads  │              │  Reads
           └──────────────┘
```

### **How It Works**

**Both masters can:**
- Accept writes
- Accept reads
- Replicate to each other (bidirectional)

**Timeline:**
```
T=0:   User in US writes to Master-A
T=1:   Master-A saves locally
T=2:   Master-A returns success
T=50:  Master-A replicates to Master-B (async)

T=100: User in EU writes to Master-B
T=101: Master-B saves locally
T=102: Master-B returns success
T=150: Master-B replicates to Master-A (async)

Both masters are active simultaneously
```

### **Use Cases**

**1. Multi-Region Setup:**
```
US Users → Master-US (low latency: 10ms)
EU Users → Master-EU (low latency: 10ms)

vs Master-Slave:
US Users → Master-US (10ms)
EU Users → Master-US (150ms - slow!)
```

**2. High Availability:**
```
Both masters active:
- If Master-A fails → traffic goes to Master-B (instant!)
- No promotion needed (already accepting writes)
- Zero failover time
```

**3. Load Distribution:**
```
10,000 writes/sec needed
Master-Slave: All 10,000 through one master (bottleneck!)
Master-Master: 5,000 each (distributed!)
```

---

### **The Conflict Problem**

**Most critical challenge in Master-Master replication**

**Scenario: Concurrent Writes**

```
Same key written on both masters simultaneously:

T=0:   User A (US) → Master-A: UPDATE account SET status='active'
T=0:   User B (EU) → Master-B: UPDATE account SET status='suspended'

T=1:   Both masters save locally
       Master-A has: status='active'
       Master-B has: status='suspended'

T=100: Replication happens
       Master-A receives: status='suspended' (from B)
       Master-B receives: status='active' (from A)
       
       CONFLICT! Which value is correct?
```

**Without conflict resolution:**
```
Masters can end up in inconsistent states:
Master-A: status='active'
Master-B: status='suspended'

Different users see different data!
System is broken! ❌
```

---

### **Conflict Resolution Strategies**

#### **1. Last-Write-Wins (LWW)**

**How it works:**
- Attach timestamp to each write
- When conflict detected, keep the write with latest timestamp
- Discard the earlier write

**Example:**
```
Master-A: status='active'   (timestamp: 1000.000)
Master-B: status='suspended' (timestamp: 1000.050)

Compare timestamps: 1000.050 > 1000.000
→ Keep 'suspended'
→ Discard 'active'

Both masters converge to: status='suspended'
```

**Problems:**
```
1. Clock skew:
   Master-A clock: 10:00:00
   Master-B clock: 10:01:00 (1 minute ahead)
   
   T=10:00:00: Master-A writes (timestamp: 1000)
   T=10:00:30: Master-B writes (timestamp: 1060 - wrong!)
   
   LWW incorrectly chooses Master-B (older write!)

2. Data loss:
   User A's write is silently discarded
   No notification that their change was lost
```

**When acceptable:**
- Non-critical data (cache, session data)
- Where "any value" is better than "no value"
- Shopping cart (losing one item better than cart failure)

#### **2. Version Vectors (Causality Tracking)**

**How it works:**
- Each write has a version vector: `{Master-A: 5, Master-B: 3}`
- Tracks how many writes each master has made to this key
- Can detect if writes are concurrent or causal

**Example:**
```
Initial: version={A:0, B:0}

Master-A writes: version={A:1, B:0}
Master-B writes: version={A:0, B:1}

When they sync:
Master-A receives version={A:0, B:1}
  Compare: {A:1, B:0} vs {A:0, B:1}
  Neither dominates → CONCURRENT CONFLICT!
  
Master-B receives version={A:1, B:0}
  Compare: {A:0, B:1} vs {A:1, B:0}
  Neither dominates → CONCURRENT CONFLICT!

Both detected the conflict
→ Can use application logic to resolve
→ Or keep both as "siblings" for user to choose
```

**Benefits:**
- Detects true conflicts (not false positives from clock skew)
- Can determine causality (did A happen before B?)
- More accurate than timestamps

**Drawbacks:**
- More complex to implement
- Requires application to handle conflicts
- Storage overhead (version vector per key)

#### **3. CRDTs (Conflict-Free Replicated Data Types)**

**How it works:**
- Special data structures that mathematically guarantee convergence
- Merging is commutative, associative, idempotent
- No conflicts possible!

**Example: G-Counter (Grow-only counter)**
```
Structure:
{
  Master-A: 5,  // Master-A incremented 5 times
  Master-B: 3   // Master-B incremented 3 times
}

Value = sum(all counts) = 5 + 3 = 8

Concurrent increments:
Master-A: increments → {A:6, B:3}
Master-B: increments → {A:5, B:4}

When they merge:
{A: max(6,5), B: max(3,4)} = {A:6, B:4}
Value = 6 + 4 = 10 ✓

Both converge to same value automatically!
```

**Benefits:**
- Zero conflicts
- Automatic convergence
- Simple to reason about

**Drawbacks:**
- Limited data types (counters, sets, maps)
- Can't do arbitrary operations
- More memory overhead

#### **4. Application-Level Resolution**

**How it works:**
- Detect conflict
- Keep both versions
- Application (or user) decides

**Example: Google Docs**
```
User A types: "Hello world"
User B types: "Goodbye world" (simultaneously)

System detects conflict:
→ Keep both versions as branches
→ Show user: "Conflict detected, which version?"
   [ ] Hello world
   [ ] Goodbye world
   [ ] Merge both

User chooses or manually merges
```

**Benefits:**
- Flexible (can implement any logic)
- User has control
- No data loss

**Drawbacks:**
- Requires user intervention
- Complex UI
- Not always possible (e.g., automated systems)

---

### **When to Use Master-Master**

✅ **Good fit:**
- Multi-region deployment (low latency everywhere)
- High write throughput needed (distribute writes)
- Zero downtime requirement (both always active)
- Data conflicts are rare or easily resolved

❌ **Bad fit:**
- Financial transactions (conflicts unacceptable)
- Inventory systems (can't oversell)
- Sequential operations (order matters)
- Simple deployments (overhead not worth it)

---

### **Real-World Examples**

**Master-Master (Multi-Master):**
- **MySQL Group Replication** - multiple writable masters
- **PostgreSQL BDR** (Bi-Directional Replication)
- **CockroachDB** - distributed SQL with multi-master
- **Cassandra** - every node is a master (masterless)
- **DynamoDB** - multi-region with conflict resolution
- **Riak** - eventually consistent multi-master

**Master-Slave:**
- **MySQL with replicas** - most common setup
- **PostgreSQL with streaming replication**
- **MongoDB replica sets** - 1 primary, N secondaries
- **Redis replication** - master-slave mode
- **Elasticsearch** - primary-replica shards

---

## **Comparison Summary**

| Aspect | Master-Slave | Master-Master |
|--------|--------------|---------------|
| **Write path** | All writes → 1 master | Writes → any master |
| **Write scalability** | Limited (single bottleneck) | Better (distributed) |
| **Read scalability** | Excellent (add slaves) | Good (both can read) |
| **Consistency** | Easier (one writer) | Complex (conflicts!) |
| **Conflict resolution** | Not needed | Critical requirement |
| **Failover time** | 30-120 seconds (promote slave) | 0 seconds (already active) |
| **Complexity** | Low | High |
| **Data loss risk** | Yes (if async) | Yes + conflicts |
| **Latency (writes)** | Good (1 master location) | Excellent (write anywhere) |
| **Use case** | Most databases | Multi-region, high availability |

---

Want me to continue with **Availability in Numbers** next?