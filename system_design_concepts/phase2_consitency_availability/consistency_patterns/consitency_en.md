# Phase 2 — Consistency & Availability

Let me break down each pattern with clear explanations, real-world examples, and practical implementation details.

---

## Part 1: Consistency Patterns

### **Weak Consistency**

**Definition:** 
After a write, reads may or may not see the new value. There's **no guarantee** when or if the data will become visible to all readers.

**Key characteristics:**
- Best effort delivery
- No synchronization guarantees
- Lowest latency, highest availability
- Data loss is acceptable

---

**Real-world examples:**

**1. VoIP/Video calls (Zoom, Discord)**
```
Time: 0ms  → You speak: "Hello world"
Time: 10ms → Audio packets transmitted
Time: 15ms → Packet #3 dropped (network congestion)
Time: 20ms → Recipient hears: "Hell...orld"

No retry: The dropped packet is GONE forever
Why: Real-time communication, retrying would cause delay worse than loss
```

**2. Live video streaming**
```
Frame sequence: F1, F2, F3, F4, F5
Network issue: F3 dropped

Player shows: F1 → F2 → F4 → F5 (skip F3)
User sees: Brief glitch, stream continues
No retry: Moving forward is better than pausing
```

**3. Real-time multiplayer games**
```
Player position updates:
T=0ms:  (x=10, y=20)
T=16ms: (x=12, y=22) ← packet lost
T=32ms: (x=14, y=24) ← arrives

Other players see: position "jump" from (10,20) to (14,24)
Client interpolates to smooth the jump
Weak consistency: Old position never received, game continues
```

**4. Metrics/Monitoring dashboards**
```
Server metrics every 1 second:
CPU: 45%, 47%, [LOST], 51%, 52%

Dashboard shows: slight gap in graph
Impact: Negligible (trend still visible)
Trade-off: 99.9% accuracy acceptable for 100% availability
```

---

**When to use:**
- ✅ Real-time communication (voice, video, gaming)
- ✅ Live streaming
- ✅ Monitoring/metrics (approximate data acceptable)
- ✅ IoT sensor data (occasional reading loss OK)

**When NOT to use:**
- ❌ Financial transactions
- ❌ Medical records
- ❌ Inventory systems
- ❌ Authentication/authorization

**Implementation example:**
```python
# UDP-based real-time data streaming (weak consistency)
import socket

def send_game_state(player_position):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
    message = f"{player_position.x},{player_position.y}"
    
    # Fire and forget - no acknowledgment
    sock.sendto(message.encode(), ('game-server', 9000))
    # No retry, no confirmation, no guarantee
    # If packet lost: too bad, next update in 16ms anyway
```

**Trade-offs:**
- ✅ Extremely low latency (no waiting for ACKs)
- ✅ Highest throughput (no retransmissions)
- ✅ Partition tolerant (continues during network issues)
- ❌ No durability guarantees
- ❌ Data loss possible
- ❌ Difficult to debug ("did client not receive, or did they receive?")

---

### **Eventual Consistency**

**Definition:**
After a write stops receiving updates, all replicas will **eventually** converge to the same value (given enough time without new writes). This is a **specific form of weak consistency** with a convergence guarantee.

**Key characteristics:**
- Reads may return stale data temporarily
- All replicas eventually agree
- No guaranteed time bound for convergence
- Highly available

---

**Real-world examples:**

**1. DNS (Domain Name System)**
```
Action: Update DNS record for example.com
Old IP: 1.2.3.4
New IP: 5.6.7.8

Timeline:
T=0s:     Update authoritative nameserver → 5.6.7.8 ✓
T=30s:    Regional DNS cache still has 1.2.3.4 (TTL not expired)
T=5min:   Google DNS propagates → 5.6.7.8 ✓
T=15min:  Cloudflare DNS propagates → 5.6.7.8 ✓
T=1hour:  ISP DNS caches expire → 5.6.7.8 ✓
T=24hour: All DNS servers worldwide → 5.6.7.8 ✓

During propagation: Different users resolve to different IPs
Eventually: All converge to 5.6.7.8
```

**2. Amazon S3**
```
Action: Upload new profile picture "avatar.jpg"

PUT /bucket/avatar.jpg → Returns HTTP 200 OK

Behind the scenes:
T=0ms:   Write to primary replica (US-East-1) ✓
T=50ms:  Replicate to US-West-1 ✓
T=150ms: Replicate to EU-West-1 ✓
T=300ms: Replicate to AP-Southeast-1 ✓

User A (US-East): Sees new avatar immediately
User B (EU-West): Sees old avatar for 150ms, then new
User C (Asia-Pacific): Sees old avatar for 300ms, then new

Eventually: All users see the same avatar
```

**3. Social media feed (Twitter, Facebook)**
```
You post: "Just launched my app! 🚀"

Timeline:
T=0s:    Post saved to primary database ✓
T=0.1s:  Your followers in US see the post ✓
T=0.5s:  Followers in Europe see the post ✓
T=2s:    Followers in Asia see the post ✓
T=10s:   Post appears in "Trending" feed ✓

Different followers see your post at different times
Eventually: All followers see it
```

**4. Shopping cart (Amazon, e-commerce)**
```
Device A (Mobile): Add "MacBook Pro" to cart → saved to US datacenter
Device B (Laptop): Check cart → reading from EU datacenter (stale)

Timeline:
T=0s:    Mobile adds item → US datacenter ✓
T=0.5s:  Laptop checks cart → EU datacenter (no MacBook yet)
T=2s:    Replication completes → EU datacenter has MacBook ✓
T=2.1s:  Laptop checks again → MacBook appears!

Eventually consistent across devices
```

---

**The Convergence Mechanism:**

Different systems use different techniques to achieve eventual consistency:

**1. Last-Write-Wins (LWW)**
```python
# Each write has a timestamp
# When conflict detected, keep the latest

Write A: {user_status: "online",  timestamp: 1000}
Write B: {user_status: "away",    timestamp: 1005}

Conflict detected → Compare timestamps → Keep Write B
Final state: user_status = "away"
```

**Problem:** Clock skew can cause issues
```
Server A clock: 10:00:00 (correct)
Server B clock: 09:59:00 (1 min behind)

User updates on Server A at 10:00:00 → timestamp: 1000
User updates on Server B at 10:01:00 → timestamp: 1005 (but clock shows 1004)

LWW incorrectly prefers older write!
```

**2. Version Vectors / Vector Clocks**
```python
# Track causality, not just time

Initial: {value: "hello", version: {A:0, B:0, C:0}}

Server A updates:
{value: "hello world", version: {A:1, B:0, C:0}}

Server B updates (concurrent):
{value: "hello friend", version: {A:0, B:1, C:0}}

Detect conflict: Neither version dominates the other
→ Both versions kept as "siblings"
→ Application resolves conflict (or user chooses)
```

**3. CRDTs (Conflict-free Replicated Data Types)**
```python
# Mathematical structures that guarantee convergence

# Example: G-Counter (Grow-only counter)
class GCounter:
    def __init__(self):
        self.counts = {'A': 0, 'B': 0, 'C': 0}  # Per-node counts
    
    def increment(self, node_id):
        self.counts[node_id] += 1
    
    def value(self):
        return sum(self.counts.values())
    
    def merge(self, other):
        # Take max of each node's count
        for node_id in self.counts:
            self.counts[node_id] = max(
                self.counts[node_id],
                other.counts[node_id]
            )

# Even with concurrent updates, merging always converges!
```

---

**When to use:**
- ✅ Read-heavy workloads (caching, CDN)
- ✅ Geographic distribution (multi-region apps)
- ✅ High availability required (social media, content delivery)
- ✅ Offline-first applications (mobile apps, collaborative docs)

**When NOT to use:**
- ❌ Inventory with limited stock
- ❌ Bank account balances
- ❌ Ticket booking (one seat sold once)
- ❌ Strict ordering requirements

---

**Implementation patterns:**

**Gossip Protocol:**
```python
# Nodes randomly exchange state to converge

import random
import time

class GossipNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.data = {}
    
    def gossip(self):
        while True:
            # Pick random peer
            peer = random.choice(self.peers)
            
            # Send my data
            peer.receive_gossip(self.data)
            
            # Receive peer's data
            peer_data = peer.get_data()
            
            # Merge (take newer versions)
            self.merge(peer_data)
            
            time.sleep(1)  # Gossip every second
    
    def merge(self, peer_data):
        for key, value in peer_data.items():
            if key not in self.data:
                self.data[key] = value
            elif value['timestamp'] > self.data[key]['timestamp']:
                self.data[key] = value

# Proven to converge: each gossip round spreads data exponentially
# After log(N) rounds, all nodes have all data
```

**Read-Your-Writes Consistency:**
```python
# User always sees their own writes (even if others don't yet)

class EventuallyConsistentStore:
    def __init__(self):
        self.primary = {}      # Primary storage
        self.replicas = [{}, {}]  # Eventually consistent replicas
        self.user_writes = {}  # Track where users wrote
    
    def write(self, user_id, key, value):
        # Write to primary
        self.primary[key] = value
        
        # Track that this user wrote here
        self.user_writes[user_id] = 'primary'
        
        # Async replicate (simulate delay)
        asyncio.create_task(self.replicate(key, value))
        
        return "OK"
    
    def read(self, user_id, key):
        # If user wrote this key, read from primary (their write)
        if self.user_writes.get(user_id) == 'primary':
            return self.primary.get(key)
        
        # Otherwise, read from random replica (might be stale)
        replica = random.choice(self.replicas)
        return replica.get(key)
    
    async def replicate(self, key, value):
        await asyncio.sleep(0.5)  # Simulate network delay
        for replica in self.replicas:
            replica[key] = value
```

---

**Trade-offs:**
- ✅ High availability (accepts writes even during partitions)
- ✅ Low latency (don't wait for all replicas)
- ✅ Scalable (can add replicas without impacting write performance)
- ✅ Partition tolerant
- ❌ Temporary inconsistency (stale reads possible)
- ❌ Conflict resolution complexity
- ❌ Eventual means "no time bound" (could be seconds or hours)
- ❌ Application must handle stale data gracefully

---

### **Strong Consistency**

**Definition:**
After a write completes, **all subsequent reads will see that write or a newer value**. The system behaves as if there's only one copy of the data.

**Key characteristics:**
- Linearizability: operations appear instantaneous
- No stale reads
- Simple to reason about (like a single-threaded program)
- Lower availability during partitions

---

**Real-world examples:**

**1. Banking system (account balance)**
```
Initial balance: $1000

Transaction sequence:
T1: ATM A withdraws $100 at 10:00:00.000
T2: ATM B checks balance at 10:00:00.001
T3: ATM C withdraws $50 at 10:00:00.002

With strong consistency:
T1 completes → Balance = $900 (ALL ATMs see $900 immediately)
T2 reads → $900 ✓ (sees T1's write)
T3 completes → Balance = $850 (ALL ATMs see $850 immediately)

No ATM can ever see stale balance
Impossible to overdraw by reading old balance
```

**2. Your ticket booking system**
```
Concert venue: 1 seat remaining (Seat A1)

Timeline:
10:00:00.000 - User Alice: GET /seat/A1/status
              Response: "available" ✓

10:00:00.100 - User Alice: POST /book/seat/A1
              System locks seat
              Processes payment
              Commits booking
              Response: "Success" ✓

10:00:00.150 - User Bob: GET /seat/A1/status
              Response: "sold" ✓ (sees Alice's write immediately)

10:00:00.200 - User Bob: POST /book/seat/A1
              Response: "Already sold" ✓

Strong consistency prevents double-booking!
```

**3. Trading platform (order book)**
```
Stock price: $100
User places: SELL 10 shares @ $102

Order book must update atomically:
Before: Best ask = $105
After:  Best ask = $102 (ALL users see this immediately)

If eventual consistency:
  Some users see $102
  Other users see $105
  → Arbitrage opportunity!
  → Market unfair!

Strong consistency ensures: All traders see same price
```

**4. Distributed lock (leader election)**
```
5 nodes need to elect a leader

With strong consistency (using Raft/Paxos):
  Node A proposes: "I am leader"
  Majority (3/5) must acknowledge
  Once acknowledged: ALL nodes know Node A is leader
  No possibility of split-brain (two leaders)

With eventual consistency:
  Node A: "I am leader"
  Node B: "I am leader" (doesn't know about A yet)
  → TWO LEADERS! System broken ❌
```

---

**How it's implemented:**

**1. Synchronous replication**
```python
def write_with_strong_consistency(key, value):
    # Step 1: Acquire distributed lock
    lock = acquire_lock(key)
    
    try:
        # Step 2: Write to primary
        primary.write(key, value)
        
        # Step 3: Replicate to ALL replicas synchronously
        for replica in replicas:
            success = replica.write(key, value)
            if not success:
                raise ReplicationError("Replica unavailable")
        
        # Step 4: Wait for ALL acknowledgments
        # (Blocking here ensures consistency)
        
        # Step 5: Commit
        primary.commit(key, value)
        for replica in replicas:
            replica.commit(key, value)
        
        return "Success"
    
    finally:
        # Step 6: Release lock
        release_lock(lock)

# Total time: Sum of all replica write times
# Latency: High
# Consistency: Strong ✓
```

**2. Consensus protocols (Raft, Paxos)**
```python
# Raft consensus for distributed log

class RaftNode:
    def replicate_log_entry(self, entry):
        # Step 1: Leader proposes entry to followers
        responses = []
        for follower in self.followers:
            ack = follower.append_entry(entry)
            responses.append(ack)
        
        # Step 2: Wait for majority acknowledgment
        if len([r for r in responses if r.success]) >= (len(self.followers) + 1) // 2:
            # Majority confirmed → commit
            self.commit_entry(entry)
            
            # Step 3: Notify followers to commit
            for follower in self.followers:
                follower.commit_entry(entry)
            
            return "Committed"
        else:
            # Couldn't reach majority → reject write
            return "Failed - no quorum"

# Guarantees:
# - Once committed, entry will never be lost
# - All nodes eventually have same log (strong consistency)
# - During partition: minority partition can't commit (availability ↓)
```

**3. Two-Phase Commit (2PC)**
```python
# Distributed transaction across multiple databases

class TransactionCoordinator:
    def execute_distributed_transaction(self, operations):
        # PHASE 1: PREPARE
        prepare_votes = []
        
        for db in databases:
            # Ask: "Can you commit this?"
            vote = db.prepare(operations)
            prepare_votes.append(vote)
        
        # Check if ALL voted YES
        if all(vote == "YES" for vote in prepare_votes):
            # PHASE 2: COMMIT
            for db in databases:
                db.commit()
            return "Transaction committed"
        else:
            # ANY voted NO → abort on all
            for db in databases:
                db.abort()
            return "Transaction aborted"

# Example: Transfer $100 from Account A to Account B
# Database 1: Debit Account A
# Database 2: Credit Account B
# 
# Both must succeed, or both must fail
# Strong consistency: All DBs have same state
```

**4. Quorum reads and writes**
```python
# N = total replicas
# W = write quorum (how many must acknowledge write)
# R = read quorum (how many must be read from)
# 
# Strong consistency when: R + W > N

# Example: N=5, W=3, R=3
# (3 + 3 = 6 > 5, so overlap guaranteed)

def strong_consistent_write(key, value):
    N = 5
    W = 3
    
    acks = 0
    for replica in all_replicas:
        if replica.write(key, value):
            acks += 1
        if acks >= W:
            return "Success"  # Got enough acks
    
    return "Failed"  # Couldn't reach quorum

def strong_consistent_read(key):
    N = 5
    R = 3
    
    responses = []
    for replica in all_replicas:
        value = replica.read(key)
        responses.append(value)
        if len(responses) >= R:
            break
    
    # Return most recent value (by timestamp/version)
    return max(responses, key=lambda x: x.timestamp)

# Because R + W > N, read quorum MUST overlap with write quorum
# Therefore, read always sees the latest write
```

---

**When to use:**
- ✅ Financial systems (banking, payments, trading)
- ✅ Inventory management (limited stock)
- ✅ Booking systems (hotels, flights, tickets)
- ✅ Critical metadata (user permissions, configuration)
- ✅ Leader election / distributed coordination

**When NOT to use:**
- ❌ High-availability requirements (social media feeds)
- ❌ Geographically distributed reads (too much latency)
- ❌ High-throughput writes (synchronous replication is slow)
- ❌ Systems that must work during network partitions

---

**Trade-offs:**
- ✅ Simple to reason about (acts like single machine)
- ✅ No data conflicts
- ✅ No stale reads
- ✅ Strong correctness guarantees
- ❌ Higher latency (wait for synchronization)
- ❌ Lower availability (can't serve during partitions)
- ❌ Lower throughput (synchronous replication bottleneck)
- ❌ Not partition tolerant (CP, not AP)
- ❌ Single point of failure (if primary down, no writes)

---

## Consistency Spectrum Summary

```
Weak ←────────── Eventual ←────────── Strong
│                   │                    │
│                   │                    │
Fast, Available     Balanced            Slow, Consistent
No guarantees       Eventually same     Always same
VoIP, Gaming        Social media        Banking, Trading
```

**Choosing the right consistency model:**

| Use Case | Model | Why |
|----------|-------|-----|
| Live video streaming | Weak | Dropped frames acceptable, low latency critical |
| Social media feed | Eventual | Stale posts OK for seconds, high availability needed |
| E-commerce catalog | Eventual | Price changes can propagate slowly |
| Shopping cart | Eventual (with read-your-writes) | User sees their own changes immediately |
| Inventory (limited stock) | Strong | Can't oversell |
| Bank transfers | Strong | Cannot lose or duplicate money |
| Ticket booking | Strong | One seat sold only once |
| User authentication | Strong | Security critical |
| Metrics dashboard | Weak | Approximate data acceptable |
| DNS | Eventual | High availability > perfect consistency |
| Distributed locks | Strong | Exactly one lock holder |

---

**(To be continued in next message with Availability Patterns...)**

Ready for me to continue with Availability Patterns (Fail-over, Replication, Availability in numbers)?