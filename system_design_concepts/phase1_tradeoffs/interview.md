# Phase 1 Interview Questions for Senior Software Engineer

Here are realistic questions you might face, organized by difficulty:

---

## **Level 1: Conceptual Understanding**

### Question 1: Trade-offs Explanation
**"Explain the difference between performance and scalability. Give an example where a system has good performance but poor scalability."**

**What they're testing:**
- Can you articulate basic concepts clearly?
- Do you understand the practical implications?

**Strong answer structure:**
```
1. Define both terms clearly
2. Give concrete example from your experience
3. Explain the trade-off/relationship
```

**Example answer:**
"Performance is how fast a system responds to a single request, while scalability is how well it maintains that performance as load increases. 

For example, I worked on a video processing pipeline that could analyze a frame in 15ms - excellent performance. But we used a single-threaded architecture with a global lock. When we added more cameras, processing time degraded to 200ms because threads competed for the lock. Good performance, poor scalability.

We fixed it by sharding cameras across multiple processes and using lock-free data structures, which allowed us to scale linearly to 100+ cameras."

---

### Question 2: Latency vs Throughput
**"You're building a log aggregation system. Your manager wants to optimize for throughput. What trade-offs might you make with latency, and is this the right choice?"**

**What they're testing:**
- Understanding the inverse relationship
- Business context awareness
- Critical thinking (challenging requirements)

**Strong answer:**
"For log aggregation, optimizing for throughput makes sense because:

1. **Batching**: I'd batch 1000 logs before writing to disk instead of writing each immediately. This increases per-log latency from 5ms to maybe 500ms, but throughput jumps from 200 logs/sec to 10K logs/sec due to:
   - Fewer disk seeks
   - Better compression on batches
   - Network request amortization

2. **Async processing**: Queue logs in memory, return immediately to caller. Process asynchronously in background.

3. **Trade-off analysis**:
   - Log data is not latency-sensitive (no user waiting)
   - Losing 500ms latency for 50x throughput is worth it
   - Exception: critical alerts might need a separate low-latency path

However, I'd validate this with the team. If we're doing real-time anomaly detection on logs, we might need a hybrid approach: batch for bulk writes, but stream critical events separately."

---

### Question 3: CAP in Practice
**"Our MySQL database has a primary in US-East and a replica in EU-West. A network partition occurs. Walk me through what happens and what trade-off we've made."**

**What they're testing:**
- CAP theorem application to real systems
- Understanding of replication modes
- Problem-solving under failure scenarios

**Strong answer:**
"This depends on our replication configuration:

**Scenario A: Asynchronous replication (AP choice)**
- Primary in US-East continues accepting writes
- EU replica can't receive updates during partition
- EU replica serves stale reads to EU users
- Trade-off: Availability maintained, consistency temporarily lost
- When partition heals: replica catches up (eventual consistency)

**Scenario B: Synchronous replication (CP choice)**
- Primary in US-East tries to replicate write to EU
- Replication fails due to partition
- Primary either:
  - Rejects write (if we require replica acknowledgment)
  - Or accepts write but EU is now inconsistent
- Trade-off: Consistency preferred, availability sacrificed

**My recommendation:**
For most web applications, I'd use asynchronous replication with:
- Read-after-write consistency: redirect users to primary for their own writes
- Monitoring for replication lag
- Alerting if lag exceeds threshold (e.g., 5 seconds)

For critical operations (payments, inventory), use synchronous replication or single-region transactions."

---

## **Level 2: System Design Application**

### Question 4: Design Decision
**"You're designing a stock trading platform. A PM asks why orders sometimes take 50ms instead of 10ms. How do you explain the latency vs consistency trade-off?"**

**What they're testing:**
- Communication with non-technical stakeholders
- Real-world application of theory
- Problem diagnosis approach

**Strong answer:**
"Great question. Let me break down where those 40ms go:

**The 10ms scenario (best case):**
- Order hits our server: 1ms
- Validate order (balance check): 2ms
- Write to database: 5ms
- Return confirmation: 2ms
- Total: 10ms ✓

**The 50ms scenario (strong consistency):**
- Same as above: 10ms
- **Plus**: Wait for database replication to 2 replicas: 30ms
- Ensure all replicas acknowledge: 10ms
- Total: 50ms

**Why we do this:**
In trading, consistency is critical. We can't risk:
- User places order from mobile app
- Switches to web app, doesn't see their order
- Places duplicate order thinking first failed
- Now they're 2x long on a position they wanted 1x

**The trade-off:**
- 50ms latency ensures order visible immediately across all devices/regions
- Alternative: 10ms latency with 100-500ms eventual consistency
- For trading: correctness > speed

I'd show them our P50/P95/P99 latency metrics and explain that 95% of orders complete in 15ms, but we occasionally hit 50ms when replication is slower (network congestion, replica catch-up).

Would you like me to investigate if 50ms is acceptable, or should we optimize the replication strategy?"

---

### Question 5: Architecture Evolution
**"You've built a monolith that handles 1000 requests/sec with 100ms P99 latency. Traffic is growing to 10,000 requests/sec. How do you scale this? What changes to performance and latency?"**

**What they're testing:**
- Scaling strategies
- Performance implications at different scales
- Systematic thinking

**Strong answer:**
"I'd approach this in phases:

**Phase 1: Vertical scaling (quick win)**
- Current: 4 cores, 16GB RAM
- Upgrade to: 16 cores, 64GB RAM
- Expected result:
  - Handles 3000-4000 req/sec
  - Latency stays ~100ms (same code path)
  - Buys us 2-3 months
  - Cost: ~$500/month → $2000/month

**Phase 2: Horizontal scaling (sustainable)**
- Deploy 4 servers behind load balancer
- Each handles 2500 req/sec
- Expected result:
  - Total: 10,000 req/sec ✓
  - Latency might increase slightly (120ms):
    - Load balancer overhead: +10ms
    - Network hop: +10ms
  - Fault tolerance: 1 server fails, 3 continue
  - Cost: 4 × $500 = $2000/month

**Phase 3: Optimize for performance**
Since latency increased, I'd:

1. **Add caching layer (Redis)**
   - Cache hot data (user sessions, product info)
   - Reduce database queries by 60%
   - Latency drops: 120ms → 60ms

2. **Database read replicas**
   - Writes to primary
   - Reads from replicas (reduce primary load)
   - Further latency reduction: 60ms → 40ms

3. **Asynchronous processing**
   - Non-critical operations (logging, analytics) → background queue
   - Critical path latency: 40ms → 20ms

**Performance vs Scalability trade-off:**
- Initially traded performance (100ms → 120ms) for scalability
- Then optimized to get both (20ms latency at 10K req/sec)

**Monitoring:**
- Track P50, P95, P99 latency across all servers
- Alert if any server exceeds 100ms P95
- Auto-scale: add server if all servers > 80% CPU"

---

## **Level 3: Complex Scenarios**

### Question 6: Real-World Problem Solving
**"You're running a global e-commerce site. Users in Europe complain checkout is slow (2 seconds). US users report 200ms. Your database is in US-East. How do you fix this while maintaining consistency for inventory?"**

**What they're testing:**
- Multi-region architecture
- CAP theorem in practice
- Nuanced understanding of consistency requirements

**Strong answer:**
"This is a classic CAP problem. Let me break down the solution:

**Root cause:**
- Europe → US-East: ~150ms network latency
- Checkout requires multiple database round trips:
  - Check inventory: 150ms
  - Check user credit: 150ms
  - Create order: 150ms
  - Update inventory: 150ms
  - Total: ~600ms + processing
- Multiple round trips × 150ms = 2 seconds

**Solution architecture:**

**1. Read replicas in EU (for reads)**
```
EU Users → EU Read Replica (catalog, user data)
Latency: 5ms instead of 150ms ✓
```

**2. Critical writes still to US-East (for consistency)**
```
Inventory updates, order creation → US-East primary
Still 150ms, but only 1 round trip
```

**3. Optimize write path:**
Instead of:
```
Check inventory → Update inventory → Create order → Update again
(4 round trips × 150ms = 600ms)
```

Do:
```
Single transaction with all operations batched
(1 round trip × 150ms = 150ms)
```

**4. Two-phase approach:**
```
Phase 1 (Fast - EU):
- Read product details from EU replica (5ms)
- Show price, description
- Add to cart (local state)

Phase 2 (Slow - US):
- Submit checkout
- Single transaction to US-East (150ms)
- Inventory check + order creation + payment
```

**Result:**
- Browsing: 5ms (was 150ms) ✓
- Checkout: 150ms (was 2s) ✓
- Consistency maintained for inventory ✓

**Alternative (if 150ms still too slow):**

**Reserve inventory pattern:**
```
1. User clicks "checkout" → reserve inventory (150ms to US)
2. User fills payment info (20 seconds) → local UI, no database
3. User submits → confirm reservation (150ms to US)
4. Total perceived latency: only checkout button click
```

**What about eventual consistency?**

For inventory, we MUST use strong consistency (CP):
- Can't oversell limited stock
- Accept 150ms write latency
- Alternative would be: sell 100 units, have 110 orders ❌

For product catalog, eventual consistency (AP) is fine:
- Price update takes 5 seconds to reach EU ✓
- Edge case: user sees old price, checkout shows new price
- Acceptable trade-off for 30x faster browsing"

---

### Question 7: Trade-off Analysis
**"Design a distributed rate limiter that prevents users from making more than 100 API calls per minute. Should this be CP or AP? Defend your choice."**

**What they're testing:**
- Deep understanding of CAP
- Ability to argue both sides
- Recognizing there's no perfect answer

**Strong answer:**
"This is an interesting problem because both choices have merit. Let me argue both sides:

**Argument for CP (Consistency + Partition tolerance):**

*Why:*
- Rate limiting is about correctness
- If we're AP, during a partition:
  - US datacenter: user makes 100 requests ✓
  - EU datacenter: user makes 100 requests ✓
  - Total: 200 requests (2× limit violated!) ❌

*Implementation:*
```
Global counter in strongly consistent store (etcd, ZooKeeper)
- Write to counter requires majority quorum
- During partition: minority partition rejects requests
- Guarantees rate limit never exceeded
```

*Downside:*
- If counter service down → all requests blocked
- Higher latency (wait for consensus)

---

**Argument for AP (Availability + Partition tolerance):**

*Why:*
- Rate limiting is about abuse prevention, not correctness
- Better to allow 110 requests than block legitimate users
- High availability more important than perfect limits

*Implementation:*
```
Local counters per datacenter
- Each datacenter tracks independently
- Sync asynchronously
- During partition: might exceed limit by 2×
- When partition heals: counters reconcile
```

*Downside:*
- Can exceed rate limit temporarily
- Determined attacker could exploit partition

---

**My recommendation (Hybrid - AP with CP fallback):**

```python
# Per-datacenter tracking (AP - fast path)
local_count = redis_local.incr(f"rate_limit:{user_id}")

if local_count <= 80:  # 80% of limit
    return ALLOW  # Fast, local decision
    
elif local_count <= 100:
    # Approaching limit - check global
    global_count = check_global_counter()  # CP check
    if global_count <= 100:
        return ALLOW
    else:
        return BLOCK
        
else:  # local_count > 100
    return BLOCK  # Exceeded even locally
```

**Why this works:**
- 99% of requests: local check only (AP - fast, available)
- Near limit: global check (CP - accurate)
- During partition: might allow 100-120 requests (acceptable)
- Never allows unlimited requests (local counter still enforces)

**Final answer:**
I'd choose **AP with soft limits** for user-facing rate limiting, but **CP with hard limits** for critical resources (payment processing, database writes).

The context matters - rate limiting DDoS attacks vs rate limiting legitimate users are different problems."

---

### Question 8: Debugging Under Pressure
**"Production is down. Your CP system is rejecting all writes because it can't reach a quorum. How do you troubleshoot and what's your recovery plan?"**

**What they're testing:**
- Production experience
- Incident response
- Understanding of distributed systems failure modes

**Strong answer:**
"Let me walk through my incident response:

**Step 1: Immediate assessment (2 minutes)**
```bash
# Check cluster health
$ etcdctl member list
# Expected: 5 nodes, seeing only 2 online ❌

# Check network
$ ping node3.internal
$ ping node4.internal  
$ ping node5.internal
# All timing out - network partition suspected
```

**Step 2: Identify the partition (5 minutes)**
```bash
# Check which nodes can communicate
Node1 (US-East-1a) ← can reach → Node2 (US-East-1a)
Node3 (US-East-1b) ← PARTITION → Node1/Node2
Node4 (US-East-1b) ← can reach → Node3
Node5 (US-East-1c) ← PARTITION → All

# Result: 
# - Group A: Node1, Node2 (2 nodes) ❌ no quorum
# - Group B: Node3, Node4 (2 nodes) ❌ no quorum  
# - Group C: Node5 (1 node) ❌ no quorum
# Need 3/5 for quorum - nobody has it!
```

**Step 3: Root cause (3 minutes)**
```bash
# Check AWS status
# "Elevated packet loss in us-east-1b"
# AHA! Availability zone issue
```

**Step 4: Immediate mitigation options**

**Option A: Reduce quorum requirement (DANGEROUS)**
```bash
# Temporarily require 2/5 instead of 3/5
# DON'T DO THIS - risks split brain!
```

**Option B: Force single region (SAFE)**
```bash
# Stop nodes in affected AZs
systemctl stop etcd on Node3, Node4, Node5

# Now: 2/2 nodes healthy = quorum ✓
# Cluster accepts writes again
```

**Option C: Deploy new node in healthy AZ (SAFER)**
```bash
# Spin up Node6 in us-east-1a
# Add to cluster
# Now: Node1, Node2, Node6 = 3/6 = quorum ✓
```

**My choice: Option C**
- Doesn't reduce safety guarantees
- Maintains fault tolerance
- Can remove failed nodes later

**Step 5: Recovery (20 minutes)**
```bash
# 1. Deploy Node6 in us-east-1a
terraform apply -target=aws_instance.etcd_node_6

# 2. Add to cluster
etcdctl member add node6 --peer-urls=http://node6:2380

# 3. Verify quorum
etcdctl endpoint health
# node1: healthy
# node2: healthy  
# node6: healthy
# Quorum achieved! ✓

# 4. Application layer
# Restart failed writes
# Most should auto-retry
```

**Step 6: Post-incident**

**Immediate:**
- Update runbook with this scenario
- Set up alerting for AZ-level failures
- Monitor replication lag as Node3/4/5 come back

**Long-term prevention:**
```
Original: 5 nodes
- us-east-1a: Node1, Node2
- us-east-1b: Node3, Node4  
- us-east-1c: Node5

Problem: 2 nodes in same AZ = not fault tolerant enough

New architecture: 5 nodes across 3 AZs evenly
- us-east-1a: Node1, Node2
- us-east-1b: Node3
- us-east-1c: Node4, Node5

Even better: 5 nodes across 3 regions
```

**Lessons:**
1. CP systems are less available during partitions (as designed)
2. Need monitoring for quorum status
3. Chaos testing: simulate AZ failures quarterly
4. Have runbook for partial quorum scenarios

**Communication:**
- Told team: 'Network partition in us-east-1b, lost quorum'
- Not: 'Database is broken' (inaccurate)
- Set expectations: 20 min recovery time
- Posted updates every 5 minutes"

---

## **Behavioral + Technical Combo**

### Question 9: Past Experience
**"Tell me about a time you had to choose between consistency and availability in a system you built. What did you choose and why?"**

**What they're testing:**
- Real experience with trade-offs
- Decision-making process
- Learning from outcomes

**Strong answer using your projects:**
"In my fraud detection system, I faced exactly this choice:

**The problem:**
- Real-time transaction scoring (ML model)
- Multiple scoring services for redundancy
- Services in different data centers
- Question: What happens during a partition?

**Option 1: CP approach**
```python
# Require all scoring services to agree
scores = []
for service in fraud_detection_services:
    try:
        scores.append(service.score(transaction))
    except NetworkError:
        return BLOCK_TRANSACTION  # Can't reach service
        
if len(scores) < 3:  # Need all 3 services
    return BLOCK_TRANSACTION
    
return aggregate_scores(scores)
```

**Impact:**
- Pro: Never allow fraud through
- Con: Block legitimate transactions during network issues
- User impact: "Transaction declined" even though user is legitimate

**Option 2: AP approach**
```python
# Accept best-effort scoring
scores = []
for service in fraud_detection_services:
    try:
        scores.append(service.score(transaction))
    except NetworkError:
        continue  # Skip unavailable service
        
if len(scores) == 0:
    return USE_FALLBACK_RULES  # Heuristic-based
    
return aggregate_scores(scores)
```

**Impact:**
- Pro: Always process transactions
- Con: Might miss fraud during outages
- User impact: Better UX, but slightly higher fraud risk

**My decision: Hybrid approach (AP with safety rails)**
```python
scores = collect_scores_with_timeout(services, timeout=100ms)

if len(scores) >= 2:  # Have majority
    final_score = aggregate_scores(scores)
    return APPROVE if final_score < threshold else BLOCK
    
elif len(scores) == 1:  # Only one service
    # Use conservative threshold (lower risk tolerance)
    return APPROVE if score < (threshold * 0.7) else BLOCK
    
else:  # No services available
    # Fallback: rule-based scoring
    # Higher threshold for approval
    return fallback_scoring(transaction, conservative=True)
```

**Why this balance:**
1. **Business context**: 
   - Blocking legitimate user = lost sale, poor UX
   - Allowing fraud = financial loss, but insured
   - Trade-off: Slight fraud increase acceptable for availability

2. **Measured approach:**
   - Not fully CP: Don't block if 1 service down
   - Not fully AP: Don't blindly approve with no checks
   - Degrade gracefully with increasing conservatism

**Outcome:**
- 99.9% availability (vs 99.5% with CP approach)
- Fraud rate: 0.08% (vs 0.06% with CP)
- Business accepted 0.02% fraud increase for better UX
- Saved ~$50K/month in lost sales from false declines

**What I learned:**
- CAP isn't binary - you can have gradients
- Context matters: trading platform needs CP, fraud detection can be AP
- Monitor and measure: tracked fraud rate weekly to ensure trade-off valid
- Have fallbacks: rule-based scoring as safety net"

---

## **How to Prepare**

1. **For each concept, prepare:**
   - Clear definition (30 seconds)
   - Real-world example from your experience
   - Trade-off explanation
   - When to choose X vs Y

2. **Practice articulating:**
   - "Performance is X, scalability is Y, the difference is..."
   - "In my fraud detection system, I chose AP because..."
   - "The trade-off is: if we optimize for X, we sacrifice Y, which means..."

3. **Have 2-3 stories ready:**
   - Time you chose CP (trading platform, ticket booking)
   - Time you chose AP (fraud detection, chat system)
   - Time you had performance vs scalability issue (DeepStream)

4. **Mental framework for any question:**
   ```
   1. Clarify requirements (5 seconds)
   2. State trade-off explicitly (10 seconds)
   3. Argue both sides (30 seconds)
   4. Make recommendation with context (20 seconds)
   5. Discuss monitoring/validation (15 seconds)
   ```

Ready for Phase 2 questions or want to drill any of these?