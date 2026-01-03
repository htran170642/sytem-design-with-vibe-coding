# Availability in Numbers (Tính Sẵn Sàng Theo Số Liệu)

---

## **Availability là gì?**

**Định nghĩa:**
Tỷ lệ phần trăm thời gian mà hệ thống hoạt động và có thể phục vụ requests.

**Công thức:**
```
Availability = Uptime / (Uptime + Downtime)

Hoặc:

Availability = (Total Time - Downtime) / Total Time
```

**Ví dụ:**
```
Tháng có 30 ngày = 30 × 24 = 720 giờ

Downtime: 7.2 giờ
Uptime: 720 - 7.2 = 712.8 giờ

Availability = 712.8 / 720 = 0.99 = 99%
```

---

## **Bảng Availability và Downtime**

### **The Nines (Các số 9)**

| Availability | Downtime/Năm | Downtime/Tháng | Downtime/Tuần | Downtime/Ngày |
|--------------|--------------|----------------|---------------|---------------|
| **90% (one nine)** | 36.5 ngày | 3 ngày | 16.8 giờ | 2.4 giờ |
| **95%** | 18.25 ngày | 1.5 ngày | 8.4 giờ | 1.2 giờ |
| **99% (two nines)** | 3.65 ngày | 7.2 giờ | 1.68 giờ | 14.4 phút |
| **99.5%** | 1.83 ngày | 3.6 giờ | 50.4 phút | 7.2 phút |
| **99.9% (three nines)** | 8.76 giờ | 43.2 phút | 10.1 phút | 1.44 phút |
| **99.95%** | 4.38 giờ | 21.6 phút | 5.04 phút | 43.2 giây |
| **99.99% (four nines)** | 52.6 phút | 4.32 phút | 1.01 phút | 8.64 giây |
| **99.995%** | 26.3 phút | 2.16 phút | 30.2 giây | 4.32 giây |
| **99.999% (five nines)** | 5.26 phút | 25.9 giây | 6.05 giây | 0.864 giây |
| **99.9999% (six nines)** | 31.5 giây | 2.59 giây | 0.605 giây | 0.0864 giây |

### **Chi tiết các mức thường gặp:**

#### **99% (Two Nines)**
```
Downtime cho phép:
- Mỗi năm: 3.65 ngày (87.6 giờ)
- Mỗi tháng: 7.2 giờ
- Mỗi tuần: 1.68 giờ
- Mỗi ngày: 14.4 phút

Use cases:
- Internal tools (công cụ nội bộ)
- Development/staging environments
- Non-critical applications
- Personal projects

Ví dụ:
"Server có thể down khoảng 1 giờ mỗi tuần để maintenance"
```

#### **99.9% (Three Nines)**
```
Downtime cho phép:
- Mỗi năm: 8.76 giờ
- Mỗi tháng: 43.2 phút
- Mỗi tuần: 10.1 phút
- Mỗi ngày: 1.44 phút

Use cases:
- Most web applications
- Standard SaaS products
- E-commerce sites
- Mobile apps

Ví dụ:
"Website có thể down khoảng 10 phút mỗi tuần"
```

#### **99.99% (Four Nines)**
```
Downtime cho phép:
- Mỗi năm: 52.6 phút
- Mỗi tháng: 4.32 phút
- Mỗi tuần: 1.01 phút
- Mỗi ngày: 8.64 giây

Use cases:
- E-commerce platforms (Amazon, Shopify)
- Enterprise SaaS
- Payment systems
- Critical business applications

Ví dụ:
"Hệ thống chỉ có thể down dưới 1 phút mỗi tuần"
```

#### **99.999% (Five Nines)**
```
Downtime cho phép:
- Mỗi năm: 5.26 phút
- Mỗi tháng: 25.9 giây
- Mỗi tuần: 6 giây
- Mỗi ngày: 0.86 giây

Use cases:
- Banking systems
- Trading platforms
- Telecommunications
- Life-critical systems (911 services)

Ví dụ:
"Hệ thống chỉ có thể down 6 giây mỗi tuần"
```

#### **99.9999% (Six Nines)**
```
Downtime cho phép:
- Mỗi năm: 31.5 giây
- Mỗi tháng: 2.6 giây
- Mỗi tuần: 0.6 giây

Use cases:
- Medical equipment
- Air traffic control
- Nuclear power plant systems
- Extremely critical infrastructure

Ví dụ:
"Hệ thống chỉ có thể down nửa giây mỗi tuần"
```

---

## **Tính Toán Availability trong Hệ Thống Phân Tán**

### **1. Availability Tuần Tự (Sequential/Series)**

**Khi các components phải hoạt động tuần tự** (request đi qua tất cả):

```
Total Availability = Availability₁ × Availability₂ × ... × Availabilityₙ
```

**Ví dụ 1: Web Application Stack**
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

Downtime/tháng = 43.2 phút × 4 components = ~3 giờ
```

**Ví dụ 2: Microservices**
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

Downtime/tháng = ~3.6 giờ
```

**Nhận xét quan trọng:**
```
Càng nhiều components trong chuỗi → Availability càng giảm!

1 component @ 99.9%:  99.9% availability
5 components @ 99.9%: 99.5% availability
10 components @ 99.9%: 99.0% availability
20 components @ 99.9%: 98.0% availability

Bài học: Giảm số lượng dependencies cần thiết!
```

### **2. Availability Song Song (Parallel/Redundancy)**

**Khi có các components dự phòng** (chỉ cần 1 hoạt động):

```
Total Availability = 1 - (1 - Availability₁) × (1 - Availability₂) × ... × (1 - Availabilityₙ)
```

**Ví dụ 1: Hai Servers Dự Phòng**
```
[Server A] 99% availability
[Server B] 99% availability (backup)

Failure probability của A = 1 - 0.99 = 0.01 (1%)
Failure probability của B = 1 - 0.99 = 0.01 (1%)

Probability CẢ HAI fail cùng lúc = 0.01 × 0.01 = 0.0001 (0.01%)

Total Availability = 1 - 0.0001 = 0.9999 = 99.99%

Từ 99% → 99.99% chỉ bằng cách thêm 1 backup! 🎉
```

**Ví dụ 2: Ba Servers Dự Phòng**
```
[Server A] 99%
[Server B] 99%
[Server C] 99%

Probability cả 3 fail = 0.01³ = 0.000001

Total Availability = 1 - 0.000001 = 0.999999 = 99.9999% (six nines!)

Từ 99% → 99.9999% với 3 servers dự phòng!
```

**Ví dụ 3: Multi-Region Database**
```
[US-East DB] 99.9%
[US-West DB] 99.9%
[EU DB] 99.9%

Probability cả 3 regions fail = 0.001³ = 0.000000001

Total Availability ≈ 99.9999999% (nine nines!)
```

**Bảng So Sánh Redundancy:**

| Số Replicas | Availability mỗi replica | Total Availability | Downtime/năm |
|-------------|-------------------------|-------------------|--------------|
| 1 | 99% | 99% | 3.65 ngày |
| 2 | 99% | 99.99% | 52.6 phút |
| 3 | 99% | 99.9999% | 31.5 giây |
| 1 | 99.9% | 99.9% | 8.76 giờ |
| 2 | 99.9% | 99.9999% | 31.5 giây |
| 3 | 99.9% | 99.999999% | 0.3 giây |

---

## **Ví Dụ Tính Toán Thực Tế**

### **Ví dụ 1: E-commerce Platform**

**Kiến trúc:**
```
User
  ↓
CDN (99.99%)
  ↓
Load Balancer (99.99%)
  ↓
[Web Server 1] ──┐
[Web Server 2] ──┤ Active-Active (mỗi cái 99.9%)
[Web Server 3] ──┘
  ↓
[App Server 1] ──┐
[App Server 2] ──┘ Active-Passive (mỗi cái 99.9%)
  ↓
[DB Primary] ────┐
[DB Standby] ────┘ Master-Slave (mỗi cái 99.95%)
```

**Tính toán:**

**1. Web Servers (parallel):**
```
3 servers, mỗi cái 99.9%
Failure probability = 0.001³ = 0.000000001
Availability = 99.9999999% ≈ 100%
```

**2. App Servers (parallel):**
```
2 servers, mỗi cái 99.9%
Failure probability = 0.001² = 0.000001
Availability = 99.9999%
```

**3. Database (failover):**
```
Primary: 99.95%
Standby: 99.95%
Failover time: 2 minutes/month

Availability ≈ 99.95% (vì failover adds downtime)
```

**4. Total (sequential):**
```
Total = CDN × LB × Web × App × DB
      = 0.9999 × 0.9999 × 0.999999 × 0.999999 × 0.9995
      = 0.9993
      = 99.93%

Downtime/tháng = 43.2 × (1 - 0.9993/0.999)
                ≈ 30 phút
```

**Target: 99.99% (4.32 phút downtime/tháng)**

**Cách cải thiện:**
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

### **Ví dụ 2: Trading Platform**

**Requirements:**
- Must handle 10,000 trades/second
- Max latency: 10ms P99
- Target availability: 99.999% (5.26 phút/năm)
- No data loss acceptable

**Kiến trúc:**

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

Downtime/năm = 365 × 24 × 60 × 60 × 0.00000001
             = 0.3 giây/năm ✓
```

**Chi phí vs Availability:**
```
99.9% (3 nines):     $10,000/month (1 region, basic setup)
99.99% (4 nines):    $50,000/month (2 regions, redundancy)
99.999% (5 nines):   $200,000/month (3 regions, full redundancy)
99.9999% (6 nines):  $1,000,000/month (global, extreme redundancy)

Mỗi "nine" thêm vào ~ tăng cost 5-10×!
```

---

## **Những Yếu Tố Ảnh Hưởng Availability**

### **1. Planned Downtime (Downtime có kế hoạch)**

**Deployment:**
```
Traditional deployment:
- Stop service
- Deploy new code
- Start service
- Downtime: 5-10 phút

Blue-Green deployment:
- Blue (old) running
- Deploy to Green (new)
- Switch traffic to Green
- Downtime: 0 giây ✓

Rolling deployment:
- Update 1 server at a time
- Always have servers running
- Downtime: 0 giây ✓
```

**Database Migrations:**
```
Bad approach:
1. Stop application
2. Run migration (30 phút)
3. Start application
Downtime: 30 phút ❌

Good approach:
1. Make schema backward compatible
2. Deploy code that works with both schemas
3. Run migration (background)
4. Deploy code using new schema
Downtime: 0 giây ✓
```

**Maintenance Windows:**
```
Monthly maintenance: 2 giờ
Impact on 99.9%: 43.2 phút allowed
→ Already over budget! ❌

Solution: 
- Eliminate maintenance windows
- Use rolling updates
- Automate everything
```

### **2. Unplanned Downtime (Downtime không kế hoạch)**

**Hardware Failures:**
```
Hard drive: MTTF = 1,000,000 giờ (114 năm)
But with 1000 drives: 1 failure mỗi 1000 giờ (41 ngày)

Solution: RAID, redundancy, hot swaps
```

**Software Bugs:**
```
Average bug causes: 1-2 giờ downtime
Frequency: 2-4 lần/năm

99.9% budget: 8.76 giờ/năm
4 bugs × 2 giờ = 8 giờ (92% budget used!)

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
Datacenter network outage: 2-4 giờ
Frequency: 1-2 lần/năm

Impact: 
2 outages × 3 giờ = 6 giờ
99.9% budget: 8.76 giờ (68% used!)

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

## **Strategies để Đạt High Availability**

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

**Thay vì fail hoàn toàn, giảm chức năng:**

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

# User vẫn có experience, chỉ kém hơn một chút
# System vẫn available ✓
```

**Ví dụ:**
```
Amazon product page:
- Recommendations service down?
  → Show "Customers also bought" (cached)
  
- Reviews service down?
  → Hide review section
  
- Inventory service down?
  → Show "Check availability" instead of exact count

Page vẫn load được, vẫn mua hàng được ✓
```

### **3. Circuit Breakers**

**Ngăn cascade failures:**

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

**Kịch bản:**
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
**Metrics đo lường performance:**

```
Examples:
- Request latency P99 < 100ms
- Availability > 99.9%
- Error rate < 0.1%
- Throughput > 1000 RPS
```

### **SLO (Service Level Objective)**
**Target nội bộ:**

```
Our SLOs:
- API availability: 99.95%
- P99 latency: < 50ms
- Error rate: < 0.05%

Slightly stricter than SLA (buffer room)
```

### **SLA (Service Level Agreement)**
**Cam kết với customers:**

```
Our SLA:
- 99.9% uptime monthly
- P99 latency < 100ms
- If violated: 10% credit/downtime hour

Example violation:
Downtime: 2 giờ in tháng
Budget: 43.2 phút
Over by: 77 phút
Credit: 2 × 10% = 20% của monthly fee
```

**Error Budget:**
```
99.9% SLA = 0.1% allowed downtime
= 43.2 phút/tháng

Week 1: 10 phút downtime (23% budget used)
Week 2: 5 phút downtime (34% budget used)
Week 3: 20 phút downtime (81% budget used)
Week 4: 8 phút downtime (99% budget used) ⚠️

Budget almost exhausted!
→ Freeze deployments
→ Focus on stability
→ No new features until next month
```

---

## **Tóm Tắt Quan Trọng**

### **Những Điều Cần Nhớ:**

1. **Mỗi "nine" thêm vào tăng cost 5-10×**
   - 99% → 99.9%: Moderate cost
   - 99.9% → 99.99%: Expensive
   - 99.99% → 99.999%: Very expensive
   - 99.999% → 99.9999%: Extremely expensive

2. **Components tuần tự làm giảm availability**
   - 5 components @ 99.9% = 99.5% total
   - Minimize dependencies!

3. **Redundancy cải thiện availability**
   - 1 server @ 99% = 99%
   - 2 servers @ 99% = 99.99%
   - 3 servers @ 99% = 99.9999%

4. **Không cần 99.999% cho mọi thứ**
   - Internal tools: 99% OK
   - Public websites: 99.9% good
   - E-commerce: 99.99% better
   - Banking/Trading: 99.999% necessary

5. **Human errors là nguyên nhân chính**
   - Automation > manual
   - Testing > hoping
   - Monitoring > guessing

---

Bạn có muốn tôi giải thích thêm phần nào hoặc cung cấp code examples cho các strategies này không?