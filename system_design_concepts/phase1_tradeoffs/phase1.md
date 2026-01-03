# Phase 1 — Core Trade-offs

Let me break down each concept with clear explanations and real-world examples.

---

## **Performance vs Scalability**

### **Performance**
**Definition:** How fast a system responds to a single request.

**Measurement:**
- Response time (latency)
- Throughput (requests per second)
- Resource utilization (CPU, memory, disk I/O)

**Example:**
Your DeepStream video processing:
- Processing one camera feed in 30ms = good performance
- Processing it in 200ms = poor performance

### **Scalability**
**Definition:** How well a system handles increased load by adding resources.

**Types:**

#### **Vertical Scaling (Scale Up)**
Add more power to existing machine:
- More CPU cores
- More RAM
- Faster disk (SSD → NVMe)
- Better GPU

**Example:** Your DeepStream server
- 1 GPU → processes 10 cameras
- Upgrade to 2 GPUs → processes 20 cameras

**Pros:**
✅ Simple (no code changes)
✅ No distributed system complexity

**Cons:**
❌ Hardware limits (can't infinitely upgrade)
❌ Expensive (exponential cost)
❌ Single point of failure

#### **Horizontal Scaling (Scale Out)**
Add more machines:
- Load balancer distributes work
- Each machine handles subset of traffic

**Example:** Your trading platform
- 1 server handles 1,000 orders/sec
- Add 3 more servers → 4,000 orders/sec

**Pros:**
✅ Theoretically unlimited scaling
✅ Fault tolerant (one machine fails, others continue)
✅ Cost-effective (commodity hardware)

**Cons:**
❌ Application complexity (distributed state)
❌ Data consistency challenges
❌ Network overhead

### **The Key Distinction**

**A performant system serves requests quickly for a single user.**
**A scalable system maintains that performance as users increase.**

**Example:**
```
System A: Responds in 10ms with 1 user, 10ms with 1M users → Scalable ✅
System B: Responds in 10ms with 1 user, 5000ms with 1M users → Not scalable ❌
```

**Common Problem:**
A system can have good performance but poor scalability:
- Fast database queries on small dataset
- Becomes slow as data grows (missing indexes, no sharding)

---

## **Latency vs Throughput**

### **Latency**
**Definition:** Time to perform an action (from request to response).

**Measurement:** Milliseconds (ms), seconds (s)

**Examples:**
- Database query: 5ms
- API call: 100ms
- Disk seek: 10ms
- Network round-trip (US to Europe): 150ms

**Types:**
1. **Network latency:** Time for data to travel
2. **Processing latency:** Time to compute
3. **Queuing latency:** Time waiting in queue

**Your systems:**
- **Fraud detection:** P99 latency = 50ms (99% of requests under 50ms)
- **RTSP streaming:** Frame latency < 100ms for "real-time" feel
- **Trading platform:** Order placement latency < 10ms critical

### **Throughput**
**Definition:** Number of operations completed per unit time.

**Measurement:** 
- Requests per second (RPS)
- Transactions per second (TPS)
- Queries per second (QPS)
- Megabytes per second (MB/s)

**Examples:**
- Web server: 10,000 requests/sec
- Database: 5,000 writes/sec
- Kafka: 1 million messages/sec
- Your DeepStream: 30 frames/sec per camera

### **The Relationship**

**They're related but not the same!**

```
Throughput = Number of requests / Time
Latency = Time for one request
```

**Key insight:** You can have:
1. **High throughput, high latency**
   - Batch processing 1M records in 1 hour
   - Throughput: ~277 records/sec
   - Latency per record: Hours (batched)

2. **Low throughput, low latency**
   - Real-time system processes 10 requests/sec
   - Throughput: 10 RPS
   - Latency: 5ms per request

### **The Trade-off**

Often inversely related:
- **Optimizing for latency:** Process requests immediately → fewer batching opportunities
- **Optimizing for throughput:** Batch requests together → higher per-request latency

**Example from your fraud detection:**
```
Option A (Low latency):
- Process each transaction immediately
- Latency: 20ms
- Throughput: 1,000 TPS

Option B (High throughput):
- Batch 100 transactions, process together
- Latency: 500ms (wait for batch)
- Throughput: 5,000 TPS (better GPU utilization)
```

**Real-world:** Aim for "good enough" latency while maximizing throughput.

---

## **Availability vs Consistency**

### **Availability**
**Definition:** System responds to every request (even if with stale/incorrect data).

**What it means:**
- Every request gets a response
- No guarantee the response is the latest value
- System stays operational during failures

**Example:**
- Instagram feed: Shows posts even if some new posts haven't propagated
- DNS: Returns IP address (even if slightly outdated)
- Your chat system: Delivers messages even during network partitions

**Measurement:**
```
Availability = Uptime / Total Time
99.9% = 43 minutes downtime/month
99.99% = 4.3 minutes downtime/month
```

### **Consistency**
**Definition:** All nodes see the same data at the same time.

**What it means:**
- Every read receives the most recent write
- System might refuse requests to maintain correctness
- All replicas have identical data

**Example:**
- Bank account balance: Must show correct amount across all ATMs
- Your ticket booking system: Can't sell same seat twice
- Inventory: Can't oversell limited stock

**The Spectrum:**

```
Strong Consistency ←──────────────────→ Weak Consistency
(All replicas agree)                    (Replicas may differ)

Banking, Trading                        Social media, Caching
Inventory systems                       CDN, DNS
```

### **The Fundamental Trade-off**

**You cannot have both perfect availability AND perfect consistency in a distributed system during network partitions.**

This is the essence of the CAP theorem (next section).

**Examples:**

**Choose Availability (AP):**
```
Scenario: Network partition between data centers

Response: 
- Both data centers continue serving requests
- Might return stale data
- System stays available ✓
- Temporary inconsistency ✓
```
**Use case:** Social media, caching, DNS

**Choose Consistency (CP):**
```
Scenario: Network partition between data centers

Response:
- System rejects writes (can't guarantee all replicas updated)
- Only serves reads (from confirmed consistent data)
- System partially unavailable ✓
- Data stays consistent ✓
```
**Use case:** Banking, inventory, distributed databases (MongoDB in CP mode)

---

## **CAP Theorem**

**Statement:** 
In a distributed system, you can have at most **2 out of 3**:
1. **C**onsistency
2. **A**vailability  
3. **P**artition Tolerance

### **Partition Tolerance (P)**
**Definition:** System continues operating despite network partitions (messages lost/delayed between nodes).

**Reality:** Network partitions WILL happen in distributed systems.
- Switch failures
- Network congestion
- Data center connectivity issues
- DNS problems

**Therefore:** You must choose P. The real choice is between C and A during partitions.

### **The Real Trade-off: CP vs AP**

```
         Consistency (C)
              △
             ╱ ╲
            ╱   ╲
           ╱ CAP ╲
          ╱   ?   ╲
         ╱─────────╲
Availability (A) ─── Partition Tolerance (P)
                    (Must have)

Choice: CA (impossible in distributed systems)
        CP (sacrifice availability)
        AP (sacrifice consistency)
```

### **Why CA is Impossible in Distributed Systems**

**Single machine (non-distributed):**
- Can have C + A (no partitions possible)
- Example: SQLite on one server

**Distributed system:**
- Network partitions inevitable
- Must tolerate partitions (P)
- Choose C or A

---

## **CP — Consistency and Partition Tolerance**

**What it means:**
During a partition, sacrifice availability to maintain consistency.

### **Behavior During Partition**

```
Data Center 1  ┊ Network Partition ┊  Data Center 2
   (Node A)    ┊        ✗✗✗        ┊     (Node B)
               ┊                   ┊
Write arrives  ┊                   ┊
  ↓            ┊                   ┊
Can't reach B! ┊                   ┊
  ↓            ┊                   ┊
REJECT write   ┊                   ┊  Also rejects writes
(return error) ┊                   ┊  (can't sync with A)
```

**Strategy:**
1. Detect partition
2. Stop accepting writes (or only accept on majority partition)
3. Return errors to clients
4. Maintain consistency ✓
5. Reduce availability ✓

### **Real Systems (CP)**

**MongoDB (with majority write concern):**
- Write must be acknowledged by majority of replicas
- During partition: minority partition rejects writes
- Ensures consistency across surviving nodes

**HBase:**
- Region servers require connection to ZooKeeper
- Partition from ZooKeeper → stop serving requests
- Prevents split-brain scenarios

**Redis Cluster (with wait command):**
- Can be configured to wait for replica acknowledgment
- Blocks writes if replicas unreachable

**Your banking system example (CP):**
```python
# Account balance update
def transfer(from_account, to_account, amount):
    # Begin distributed transaction
    transaction = begin_transaction()
    
    try:
        # Both operations must succeed on all replicas
        debit(from_account, amount)   # Must sync to all nodes
        credit(to_account, amount)    # Must sync to all nodes
        
        # Wait for ALL replicas to acknowledge
        if not all_replicas_acknowledged():
            raise PartitionError("Cannot reach all replicas")
        
        commit(transaction)
        return "Success"
    
    except PartitionError:
        rollback(transaction)
        return "Error: System unavailable"  # Sacrifice availability
```

**Trade-offs:**
✅ Data always correct
✅ No conflicts to resolve
❌ System unavailable during partitions
❌ Higher latency (wait for acknowledgments)

---

## **AP — Availability and Partition Tolerance**

**What it means:**
During a partition, sacrifice consistency to maintain availability.

### **Behavior During Partition**

```
Data Center 1  ┊ Network Partition ┊  Data Center 2
   (Node A)    ┊        ✗✗✗        ┊     (Node B)
               ┊                   ┊
Write arrives: ┊                   ┊  Write arrives:
"status=online"┊                   ┊  "status=away"
  ↓            ┊                   ┊     ↓
Accept write   ┊                   ┊  Accept write
locally ✓      ┊                   ┊  locally ✓
               ┊                   ┊
Node A:        ┊                   ┊  Node B:
status=online  ┊                   ┊  status=away
(INCONSISTENT!)┊                   ┊  (INCONSISTENT!)
```

**After partition heals:**
```
Nodes A and B reconnect
  ↓
Detect conflict (status=online vs status=away)
  ↓
Resolve conflict:
  - Last-write-wins (timestamp)
  - Vector clocks (causality)
  - Application logic
  - Keep both (siblings)
```

### **Real Systems (AP)**

**Cassandra:**
- Eventual consistency
- Accepts writes even during partitions
- Uses vector clocks + last-write-wins
- Tunable consistency (can dial towards CP)

**DynamoDB:**
- Highly available
- Eventually consistent by default
- Conflict resolution via timestamps
- Can request strong consistency (sacrifices availability)

**Riak:**
- Focuses on availability
- Siblings (multiple versions) when conflicts
- Application resolves conflicts

**DNS:**
- Cached responses even if stale
- Availability critical (internet breaks if DNS down)
- Eventual consistency acceptable

**Your chat system example (AP):**
```python
# Message delivery
def send_message(user_id, message):
    # Write to local node immediately
    local_node.write(message)
    
    # Asynchronously replicate to other nodes
    async_replicate_to_other_nodes(message)
    
    # Return success immediately (don't wait)
    return "Message sent"  # High availability ✓

# Result:
# - Users on Node A see message immediately
# - Users on Node B see it after replication (100-500ms delay)
# - During partition: different users see different message history
# - Eventually consistent when partition heals
```

**Trade-offs:**
✅ Always available
✅ Low latency (no waiting)
✅ Partition tolerant
❌ Temporary inconsistencies
❌ Conflict resolution complexity
❌ Application must handle eventual consistency

---

## ✅ Practice Exercise

### **Explain CP vs AP using real systems**

#### **Banking System (CP)**

**Scenario:** Transfer $1000 from Account A to Account B

**Requirements:**
- Cannot lose money
- Cannot create money
- Balance must be accurate across all ATMs/branches

**Why CP?**
```
What happens during network partition?

Option 1 (AP - Wrong!):
- East branch: Deducts $1000 from Account A
- West branch: Doesn't see the deduction (partition)
- West branch: Also deducts $1000 from Account A
- Result: $2000 deducted, only $1000 credited ❌

Option 2 (CP - Correct!):
- East branch: Deducts $1000 from Account A
- Tries to sync with West branch
- Network partition detected
- Transaction REJECTED
- Return error to user: "Service temporarily unavailable"
- Result: Consistency maintained ✓, Availability sacrificed ✓
```

**Implementation:**
- Strong consistency required
- Two-phase commit
- Reject transactions during partitions
- Downtime acceptable (better than incorrect balance)

---

#### **Chat System (AP)**

**Scenario:** WhatsApp-like messaging with 1B users globally

**Requirements:**
- Messages delivered fast
- Users can send messages anytime
- Temporary message order inconsistency acceptable
- Eventual delivery guaranteed

**Why AP?**
```
What happens during network partition?

User A (USA): Sends "Hello" at 10:00:00
User B (Europe): Sends "Hi" at 10:00:01

Network partition between USA and Europe datacenters

Option 1 (CP - Bad user experience):
- System detects partition
- Blocks User A and User B from sending messages
- Users see: "Cannot send message, try again later"
- Result: Messaging app becomes unusable ❌

Option 2 (AP - Better):
- User A's message stored in USA datacenter
- User B's message stored in Europe datacenter
- Both users see "Message sent" immediately ✓
- Recipients in each region see messages in their local order
- After partition heals:
  - Messages sync globally
  - Order resolved (by timestamp or vector clock)
  - Eventual consistency ✓
```

**Trade-off accepted:**
- Different users might see messages in slightly different order temporarily
- Some users might see "User is typing..." while others don't
- Read receipts might be delayed
- **But:** App stays available and responsive ✓

**Implementation:**
- Eventual consistency
- Last-write-wins or vector clocks
- Asynchronous replication
- Offline support (messages queued locally)

---

### **Comparison Summary**

| Aspect | Banking (CP) | Chat (AP) |
|--------|-------------|-----------|
| **Priority** | Correctness | Availability |
| **During partition** | Reject requests | Accept requests |
| **User impact** | "Service unavailable" | Works normally |
| **Data guarantee** | Always correct | Eventually correct |
| **Acceptable downtime** | Minutes/hours | Milliseconds |
| **Conflict resolution** | Prevent conflicts | Resolve conflicts later |

---

### **Your Turn:**

**Design these systems - choose CP or AP:**

1. **E-commerce inventory system** (100 units of product X)
   - What happens if two users try to buy the last unit simultaneously?
   - CP or AP? Why?

2. **Collaborative document editor** (like Google Docs)
   - Two users edit the same paragraph during network partition
   - CP or AP? Why?

3. **Your fraud detection system**
   - Transaction flagged as fraudulent on one node
   - Partition prevents sync to other nodes
   - CP or AP? Why?

Write out your reasoning for each! This mental model is crucial for system design interviews.

Ready to review your answers or move to Phase 2?