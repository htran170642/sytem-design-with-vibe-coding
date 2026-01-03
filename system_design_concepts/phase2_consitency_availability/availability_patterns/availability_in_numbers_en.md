# Availability in Numbers

---

## **What is Availability?**

**Definition:**
The percentage of time that a system is operational and can serve requests.

**Formula:**
```
Availability = Uptime / (Uptime + Downtime)

Or:

Availability = (Total Time - Downtime) / Total Time
```

**Example:**
```
Month has 30 days = 30 × 24 = 720 hours

Downtime: 7.2 hours
Uptime: 720 - 7.2 = 712.8 hours

Availability = 712.8 / 720 = 0.99 = 99%
```

---

## **Availability and Downtime Table**

### **The Nines**

| Availability | Downtime/Year | Downtime/Month | Downtime/Week | Downtime/Day |
|--------------|---------------|----------------|---------------|--------------|
| **90% (one nine)** | 36.5 days | 3 days | 16.8 hours | 2.4 hours |
| **95%** | 18.25 days | 1.5 days | 8.4 hours | 1.2 hours |
| **99% (two nines)** | 3.65 days | 7.2 hours | 1.68 hours | 14.4 minutes |
| **99.5%** | 1.83 days | 3.6 hours | 50.4 minutes | 7.2 minutes |
| **99.9% (three nines)** | 8.76 hours | 43.2 minutes | 10.1 minutes | 1.44 minutes |
| **99.95%** | 4.38 hours | 21.6 minutes | 5.04 minutes | 43.2 seconds |
| **99.99% (four nines)** | 52.6 minutes | 4.32 minutes | 1.01 minutes | 8.64 seconds |
| **99.995%** | 26.3 minutes | 2.16 minutes | 30.2 seconds | 4.32 seconds |
| **99.999% (five nines)** | 5.26 minutes | 25.9 seconds | 6.05 seconds | 0.864 seconds |
| **99.9999% (six nines)** | 31.5 seconds | 2.59 seconds | 0.605 seconds | 0.0864 seconds |

### **Details of Common Levels:**

#### **99% (Two Nines)**
```
Allowed downtime:
- Per year: 3.65 days (87.6 hours)
- Per month: 7.2 hours
- Per week: 1.68 hours
- Per day: 14.4 minutes

Use cases:
- Internal tools
- Development/staging environments
- Non-critical applications
- Personal projects

Example:
"Server can be down about 1 hour per week for maintenance"
```

#### **99.9% (Three Nines)**
```
Allowed downtime:
- Per year: 8.76 hours
- Per month: 43.2 minutes
- Per week: 10.1 minutes
- Per day: 1.44 minutes

Use cases:
- Most web applications
- Standard SaaS products
- E-commerce sites
- Mobile apps

Example:
"Website can be down about 10 minutes per week"
```

#### **99.99% (Four Nines)**
```
Allowed downtime:
- Per year: 52.6 minutes
- Per month: 4.32 minutes
- Per week: 1.01 minutes
- Per day: 8.64 seconds

Use cases:
- E-commerce platforms (Amazon, Shopify)
- Enterprise SaaS
- Payment systems
- Critical business applications

Example:
"System can only be down less than 1 minute per week"
```

#### **99.999% (Five Nines)**
```
Allowed downtime:
- Per year: 5.26 minutes
- Per month: 25.9 seconds
- Per week: 6 seconds
- Per day: 0.86 seconds

Use cases:
- Banking systems
- Trading platforms
- Telecommunications
- Life-critical systems (911 services)

Example:
"System can only be down 6 seconds per week"
```

#### **99.9999% (Six Nines)**
```
Allowed downtime:
- Per year: 31.5 seconds
- Per month: 2.6 seconds
- Per week: 0.6 seconds

Use cases:
- Medical equipment
- Air traffic control
- Nuclear power plant systems
- Extremely critical infrastructure

Example:
"System can only be down half a second per week"
```

---

## **Calculating Availability in Distributed Systems**

### **1. Sequential/Series Availability**

**When components must work in sequence** (request goes through all):

```
Total Availability = Availability₁ × Availability₂ × ... × Availabilityₙ
```

**Example 1: Web Application Stack**
```
User Request
    ↓
[Load Balancer] 99.9%
    ↓
[Web Server] 99.9%
    ↓
[App Server] 99.9%
    ↓
[Database] 99.9%

Total Availability = 0.999 × 0.999 × 0.999 × 0.999
                   = 0.996
                   = 99.6%

Downtime/month = 43.2 minutes × 4 components = ~3 hours
```

**Example 2: Microservices**
```
[API Gateway] 99.9%
    ↓
[Auth Service] 99.9%
    ↓
[User Service] 99.9%
    ↓
[Payment Service] 99.9%
    ↓
[Database] 99.9%

Total = 0.999⁵ = 0.995 = 99.5%

Downtime/month = ~3.6 hours
```

**Important observation:**
```
More components in chain → Availability decreases!

1 component @ 99.9%:  99.9% availability
5 components @ 99.9%: 99.5% availability
10 components @ 99.9%: 99.0% availability
20 components @ 99.9%: 98.0% availability

Lesson: Reduce number of required dependencies!
```

### **2. Parallel/Redundancy Availability**

**When there are redundant components** (only need 1 working):

```
Total Availability = 1 - (1 - Availability₁) × (1 - Availability₂) × ... × (1 - Availabilityₙ)
```

**Example 1: Two Redundant Servers**
```
[Server A] 99% availability
[Server B] 99% availability (backup)

Failure probability of A = 1 - 0.99 = 0.01 (1%)
Failure probability of B = 1 - 0.99 = 0.01 (1%)

Probability BOTH fail simultaneously = 0.01 × 0.01 = 0.0001 (0.01%)

Total Availability = 1 - 0.0001 = 0.9999 = 99.99%

From 99% → 99.99% just by adding 1 backup! 🎉
```

**Example 2: Three Redundant Servers**
```
[Server A] 99%
[Server B] 99%
[Server C] 99%

Probability all 3 fail = 0.01³ = 0.000001

Total Availability = 1 - 0.000001 = 0.999999 = 99.9999% (six nines!)

From 99% → 99.9999% with 3 redundant servers!
```

**Example 3: Multi-Region Database**
```
[US-East DB] 99.9%
[US-West DB] 99.9%
[EU DB] 99.9%

Probability all 3 regions fail = 0.001³ = 0.000000001

Total Availability ≈ 99.9999999% (nine nines!)
```

**Redundancy Comparison Table:**

| # Replicas | Availability per replica | Total Availability | Downtime/year |
|------------|-------------------------|-------------------|---------------|
| 1 | 99% | 99% | 3.65 days |
| 2 | 99% | 99.99% | 52.6 minutes |
| 3 | 99% | 99.9999% | 31.5 seconds |
| 1 | 99.9% | 99.9% | 8.76 hours |
| 2 | 99.9% | 99.9999% | 31.5 seconds |
| 3 | 99.9% | 99.999999% | 0.3 seconds |

---

## **Real-World Calculation Examples**

### **Example 1: E-commerce Platform**

**Architecture:**
```
User
  ↓
CDN (99.99%)
  ↓
Load Balancer (99.99%)
  ↓
[Web Server 1] ──┐
[Web Server 2] ──┤ Active-Active (each 99.9%)
[Web Server 3] ──┘
  ↓
[App Server 1] ──┐
[App Server 2] ──┘ Active-Passive (each 99.9%)
  ↓
[DB Primary] ────┐
[DB Standby] ────┘ Master-Slave (each 99.95%)
```

**Calculations:**

**1. Web Servers (parallel):**
```
3 servers, each 99.9%
Failure probability = 0.001³ = 0.000000001
Availability = 99.9999999% ≈ 100%
```

**2. App Servers (parallel):**
```
2 servers, each 99.9%
Failure probability = 0.001² = 0.000001
Availability = 99.9999%
```

**3. Database (failover):**
```
Primary: 99.95%
Standby: 99.95%
Failover time: 2 minutes/month

Availability ≈ 99.95% (because failover adds downtime)
```

**4. Total (sequential):**
```
Total = CDN × LB × Web × App × DB
      = 0.9999 × 0.9999 × 0.999999 × 0.999999 × 0.9995
      = 0.9993
      = 99.93%

Downtime/month = 43.2 × (1 - 0.9993/0.999)
                ≈ 30 minutes
```

**Target: 99.99% (4.32 minutes downtime/month)**

**How to improve:**
```
1. Upgrade DB to Active-Active: 99.95% → 99.99%
   New total: 99.97%

2. Add redundant Load Balancer: 99.99% → 99.9999%
   New total: 99.97%

3. Reduce failover time: 2 min → 30 seconds
   New total: 99.98%

4. Multi-region deployment:
   US region: 99.98%
   EU region: 99.98%
   Total: 1 - (0.0002 × 0.0002) = 99.99996% ✓
```

---

### **Example 2: Trading Platform**

**Requirements:**
- Must handle 10,000 trades/second
- Max latency: 10ms P99
- Target availability: 99.999% (5.26 minutes/year)
- No data loss acceptable

**Architecture:**

```
Region 1 (US-East):
  [API Gateway] ─┬─ [Order Service] ─┬─ [Primary DB]
                 │                    └─ [Standby DB]
                 └─ [Market Data] ────── [Cache Cluster]

Region 2 (US-West):
  [API Gateway] ─┬─ [Order Service] ─┬─ [Primary DB]
                 │                    └─ [Standby DB]
                 └─ [Market Data] ────── [Cache Cluster]

Region 3 (EU-West):
  [API Gateway] ─┬─ [Order Service] ─┬─ [Primary DB]
                 │                    └─ [Standby DB]
                 └─ [Market Data] ────── [Cache Cluster]
```

**Component Availability:**
```
API Gateway (per region): 99.99% (load balanced, 3 instances)
Order Service (per region): 99.99% (5 instances)
Market Data (per region): 99.99% (distributed cache)
Database (per region): 99.95% (master-slave, sync replication)
```

**Per-Region Availability:**
```
Single region = 0.9999 × 0.9999 × 0.9999 × 0.9995
              = 0.9992
              = 99.92%
```

**Multi-Region (3 regions):**
```
All regions fail probability = 0.0008³ = 0.000000000512

Total = 1 - 0.000000000512 = 99.9999999488%
      ≈ 99.99999% (seven nines!)

Downtime/year = 365 × 24 × 60 × 60 × 0.00000001
             = 0.3 seconds/year ✓
```

**Cost vs Availability:**
```
99.9% (3 nines):     $10,000/month (1 region, basic setup)
99.99% (4 nines):    $50,000/month (2 regions, redundancy)
99.999% (5 nines):   $200,000/month (3 regions, full redundancy)
99.9999% (6 nines):  $1,000,000/month (global, extreme redundancy)

Each additional "nine" ~ 5-10× cost increase!
```

---

## **Factors Affecting Availability**

### **1. Planned Downtime**

**Deployment:**
```
Traditional deployment:
- Stop service
- Deploy new code
- Start service
- Downtime: 5-10 minutes

Blue-Green deployment:
- Blue (old) running
- Deploy to Green (new)
- Switch traffic to Green
- Downtime: 0 seconds ✓

Rolling deployment:
- Update 1 server at a time
- Always have servers running
- Downtime: 0 seconds ✓
```

**Database Migrations:**
```
Bad approach:
1. Stop application
2. Run migration (30 minutes)
3. Start application
Downtime: 30 minutes ❌

Good approach:
1. Make schema backward compatible
2. Deploy code that works with both schemas
3. Run migration (background)
4. Deploy code using new schema
Downtime: 0 seconds ✓
```

**Maintenance Windows:**
```
Monthly maintenance: 2 hours
Impact on 99.9%: 43.2 minutes allowed
→ Already over budget! ❌

Solution: 
- Eliminate maintenance windows
- Use rolling updates
- Automate everything
```

### **2. Unplanned Downtime**

**Hardware Failures:**
```
Hard drive: MTTF = 1,000,000 hours (114 years)
But with 1000 drives: 1 failure every 1000 hours (41 days)

Solution: RAID, redundancy, hot swaps
```

**Software Bugs:**
```
Average bug causes: 1-2 hours downtime
Frequency: 2-4 times/year

99.9% budget: 8.76 hours/year
4 bugs × 2 hours = 8 hours (92% of budget used!)

Solution:
- Better testing
- Canary deployments
- Feature flags
- Quick rollback
```

**Human Errors:**
```
Most common cause of downtime!

Examples:
- Fat finger: rm -rf / production ❌
- Wrong config: route all traffic to 1 server ❌
- Accidental delete: DROP DATABASE production ❌

Solutions:
- Automation (reduce manual steps)
- Multi-stage deployments
- Confirmation prompts
- Backup/restore procedures
```

**Network Issues:**
```
Datacenter network outage: 2-4 hours
Frequency: 1-2 times/year

Impact: 
2 outages × 3 hours = 6 hours
99.9% budget: 8.76 hours (68% used!)

Solution: Multi-datacenter, multi-region
```

**DDoS Attacks:**
```
Large DDoS: Can take down entire region
Duration: Hours to days

Solution:
- DDoS protection (Cloudflare, AWS Shield)
- Rate limiting
- Geographic distribution
```

---

## **Strategies to Achieve High Availability**

### **1. Eliminate Single Points of Failure (SPOF)**

**Bad:**
```
[Single Load Balancer] ← SPOF!
        ↓
    [Servers]
```

**Good:**
```
[LB 1] ──┐
[LB 2] ──┤ → [Servers]
[LB 3] ──┘
```

**Checklist:**
```
□ Multiple load balancers
□ Multiple application servers
□ Database replication
□ Multiple availability zones
□ Multiple regions (for critical systems)
□ Redundant network paths
□ Multiple power supplies
□ Backup generators
```

### **2. Graceful Degradation**

**Instead of complete failure, reduce functionality:**

```python
def get_user_recommendations():
    try:
        # Try ML recommendation service
        return ml_service.get_recommendations()
    except ServiceUnavailable:
        # Fallback to simple algorithm
        return simple_recommendations()
    except Exception:
        # Last resort: popular items
        return get_popular_items()

# User still has experience, just slightly degraded
# System remains available ✓
```

**Examples:**
```
Amazon product page:
- Recommendations service down?
  → Show "Customers also bought" (cached)
  
- Reviews service down?
  → Hide review section
  
- Inventory service down?
  → Show "Check availability" instead of exact count

Page still loads, can still purchase ✓
```

### **3. Circuit Breakers**

**Prevent cascade failures:**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
    
    def call(self, func):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit is OPEN")
        
        try:
            result = func()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e
```

**Scenario:**
```
Database slow → timeouts → circuit opens
→ Stop sending requests to DB (fast fail)
→ Return cached data or error
→ Prevent overloading DB further
→ Allow DB to recover

After timeout:
→ Try 1 request (half-open)
→ If success: close circuit, resume normal
→ If fail: open circuit again
```

### **4. Health Checks & Monitoring**

**Layers of health checks:**

```
1. Infrastructure:
   - CPU < 80%
   - Memory < 85%
   - Disk < 90%

2. Application:
   - /health endpoint returns 200
   - Can connect to database
   - Can read from cache

3. Business logic:
   - Can process sample transaction
   - API latency < 100ms P99
   - Error rate < 0.1%

4. End-to-end:
   - Synthetic transactions
   - Simulate real user flows
   - Monitor from multiple locations
```

**Monitoring stack:**
```
Metrics: Prometheus, Datadog, CloudWatch
Logs: ELK Stack, Splunk, Loki
Traces: Jaeger, Zipkin
Alerts: PagerDuty, Opsgenie
Dashboards: Grafana, Kibana
```

---

## **SLA, SLO, SLI**

### **SLI (Service Level Indicator)**
**Metrics that measure performance:**

```
Examples:
- Request latency P99 < 100ms
- Availability > 99.9%
- Error rate < 0.1%
- Throughput > 1000 RPS
```

### **SLO (Service Level Objective)**
**Internal targets:**

```
Our SLOs:
- API availability: 99.95%
- P99 latency: < 50ms
- Error rate: < 0.05%

Slightly stricter than SLA (buffer room)
```

### **SLA (Service Level Agreement)**
**Commitment to customers:**

```
Our SLA:
- 99.9% uptime monthly
- P99 latency < 100ms
- If violated: 10% credit per downtime hour

Example violation:
Downtime: 2 hours in month
Budget: 43.2 minutes
Over by: 77 minutes
Credit: 2 × 10% = 20% of monthly fee
```

**Error Budget:**
```
99.9% SLA = 0.1% allowed downtime
= 43.2 minutes/month

Week 1: 10 min downtime (23% budget used)
Week 2: 5 min downtime (34% budget used)
Week 3: 20 min downtime (81% budget used)
Week 4: 8 min downtime (99% budget used) ⚠️

Budget almost exhausted!
→ Freeze deployments
→ Focus on stability
→ No new features until next month
```

---

## **Critical Summary**

### **Key Takeaways:**

1. **Each additional "nine" increases cost 5-10×**
   - 99% → 99.9%: Moderate cost
   - 99.9% → 99.99%: Expensive
   - 99.99% → 99.999%: Very expensive
   - 99.999% → 99.9999%: Extremely expensive

2. **Sequential components reduce availability**
   - 5 components @ 99.9% = 99.5% total
   - Minimize dependencies!

3. **Redundancy improves availability**
   - 1 server @ 99% = 99%
   - 2 servers @ 99% = 99.99%
   - 3 servers @ 99% = 99.9999%

4. **Don't need 99.999% for everything**
   - Internal tools: 99% OK
   - Public websites: 99.9% good
   - E-commerce: 99.99% better
   - Banking/Trading: 99.999% necessary

5. **Human errors are the main cause**
   - Automation > manual
   - Testing > hoping
   - Monitoring > guessing

---

Would you like me to provide code examples for these strategies or continue with the next phase?