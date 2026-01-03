# Phần 1: Các Mẫu Nhất Quán (Consistency Patterns)

---

## **Nhất Quán Yếu (Weak Consistency)**

**Định nghĩa:** 
Sau khi ghi dữ liệu, các lần đọc có thể thấy hoặc không thấy giá trị mới. **Không có đảm bảo** khi nào hoặc liệu dữ liệu có trở nên visible với tất cả các reader hay không.

**Đặc điểm chính:**
- Giao hàng tận lực (best effort delivery)
- Không có đảm bảo đồng bộ hóa
- Độ trễ thấp nhất, tính sẵn sàng cao nhất
- Mất dữ liệu là chấp nhận được

---

**Ví dụ thực tế:**

**1. Cuộc gọi VoIP/Video (Zoom, Discord)**
```
Thời gian: 0ms  → Bạn nói: "Hello world"
Thời gian: 10ms → Các gói âm thanh được truyền đi
Thời gian: 15ms → Gói #3 bị mất (tắc nghẽn mạng)
Thời gian: 20ms → Người nhận nghe: "Hell...orld"

Không thử lại: Gói bị mất đã MẤT vĩnh viễn
Tại sao: Giao tiếp thời gian thực, thử lại sẽ gây độ trễ tệ hơn mất dữ liệu
```

**2. Stream video trực tiếp**
```
Chuỗi frame: F1, F2, F3, F4, F5
Vấn đề mạng: F3 bị mất

Player hiển thị: F1 → F2 → F4 → F5 (bỏ qua F3)
User thấy: Giật hình ngắn, stream tiếp tục
Không thử lại: Tiến về phía trước tốt hơn là tạm dừng
```

**3. Game multiplayer thời gian thực**
```
Cập nhật vị trí người chơi:
T=0ms:  (x=10, y=20)
T=16ms: (x=12, y=22) ← gói tin bị mất
T=32ms: (x=14, y=24) ← đến nơi

Người chơi khác thấy: vị trí "nhảy" từ (10,20) tới (14,24)
Client nội suy để làm mượt cú nhảy
Weak consistency: Vị trí cũ không bao giờ nhận được, game vẫn tiếp tục
```

**4. Dashboard metrics/giám sát**
```
Metrics server mỗi 1 giây:
CPU: 45%, 47%, [BỊ MẤT], 51%, 52%

Dashboard hiển thị: khoảng trống nhỏ trong biểu đồ
Tác động: Không đáng kể (xu hướng vẫn nhìn thấy được)
Trade-off: Độ chính xác 99.9% chấp nhận được để có 100% availability
```

---

**Khi nào dùng:**
- ✅ Giao tiếp thời gian thực (voice, video, gaming)
- ✅ Live streaming
- ✅ Giám sát/metrics (dữ liệu gần đúng chấp nhận được)
- ✅ Dữ liệu cảm biến IoT (mất vài reading thỉnh thoảng OK)

**Khi nào KHÔNG dùng:**
- ❌ Giao dịch tài chính
- ❌ Hồ sơ y tế
- ❌ Hệ thống inventory
- ❌ Xác thực/phân quyền

**Ví dụ implementation:**
```python
# Streaming dữ liệu thời gian thực dựa trên UDP (weak consistency)
import socket

def send_game_state(player_position):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
    message = f"{player_position.x},{player_position.y}"
    
    # Bắn và quên - không có xác nhận
    sock.sendto(message.encode(), ('game-server', 9000))
    # Không retry, không confirmation, không đảm bảo
    # Nếu gói tin mất: thôi kệ, cập nhật tiếp theo trong 16ms nữa
```

**Trade-offs:**
- ✅ Độ trễ cực thấp (không đợi ACK)
- ✅ Throughput cao nhất (không retransmission)
- ✅ Chịu được partition (tiếp tục khi có vấn đề mạng)
- ❌ Không có đảm bảo durability
- ❌ Có thể mất dữ liệu
- ❌ Khó debug ("client không nhận được, hay đã nhận?")

---

## **Nhất Quán Cuối Cùng (Eventual Consistency)**

**Định nghĩa:**
Sau khi một write ngừng nhận cập nhật, tất cả các replica sẽ **cuối cùng** hội tụ về cùng một giá trị (cho đủ thời gian mà không có write mới). Đây là **một dạng cụ thể của weak consistency** có đảm bảo hội tụ.

**Đặc điểm chính:**
- Các lần đọc có thể trả về dữ liệu cũ tạm thời
- Tất cả replica cuối cùng đồng ý
- Không có đảm bảo thời gian hội tụ
- Tính sẵn sàng cao

---

**Ví dụ thực tế:**

**1. DNS (Domain Name System)**
```
Hành động: Cập nhật bản ghi DNS cho example.com
IP cũ: 1.2.3.4
IP mới: 5.6.7.8

Timeline:
T=0s:     Cập nhật authoritative nameserver → 5.6.7.8 ✓
T=30s:    DNS cache vùng vẫn có 1.2.3.4 (TTL chưa hết hạn)
T=5phút:  Google DNS cập nhật → 5.6.7.8 ✓
T=15phút: Cloudflare DNS cập nhật → 5.6.7.8 ✓
T=1giờ:   Cache DNS của ISP hết hạn → 5.6.7.8 ✓
T=24giờ:  Tất cả DNS server toàn cầu → 5.6.7.8 ✓

Trong quá trình cập nhật: Các user khác nhau resolve tới IP khác nhau
Cuối cùng: Tất cả hội tụ về 5.6.7.8
```

**2. Amazon S3**
```
Hành động: Upload ảnh đại diện mới "avatar.jpg"

PUT /bucket/avatar.jpg → Trả về HTTP 200 OK

Đằng sau hậu trường:
T=0ms:   Ghi vào replica chính (US-East-1) ✓
T=50ms:  Replicate tới US-West-1 ✓
T=150ms: Replicate tới EU-West-1 ✓
T=300ms: Replicate tới AP-Southeast-1 ✓

User A (US-East): Thấy avatar mới ngay lập tức
User B (EU-West): Thấy avatar cũ trong 150ms, sau đó mới
User C (Asia-Pacific): Thấy avatar cũ trong 300ms, sau đó mới

Cuối cùng: Tất cả users thấy cùng avatar
```

**3. Feed mạng xã hội (Twitter, Facebook)**
```
Bạn đăng: "Vừa launch app! 🚀"

Timeline:
T=0s:    Post được lưu vào database chính ✓
T=0.1s:  Followers của bạn ở US thấy post ✓
T=0.5s:  Followers ở châu Âu thấy post ✓
T=2s:    Followers ở châu Á thấy post ✓
T=10s:   Post xuất hiện trong feed "Trending" ✓

Các followers khác nhau thấy post của bạn ở thời điểm khác nhau
Cuối cùng: Tất cả followers đều thấy
```

**4. Giỏ hàng (Amazon, e-commerce)**
```
Thiết bị A (Mobile): Thêm "MacBook Pro" vào giỏ → lưu vào datacenter US
Thiết bị B (Laptop): Kiểm tra giỏ → đọc từ datacenter EU (stale)

Timeline:
T=0s:    Mobile thêm item → datacenter US ✓
T=0.5s:  Laptop kiểm tra giỏ → datacenter EU (chưa có MacBook)
T=2s:    Replication hoàn tất → datacenter EU có MacBook ✓
T=2.1s:  Laptop kiểm tra lại → MacBook xuất hiện!

Cuối cùng nhất quán giữa các thiết bị
```

---

**Cơ chế hội tụ:**

Các hệ thống khác nhau dùng kỹ thuật khác nhau để đạt eventual consistency:

**1. Last-Write-Wins (LWW)**
```python
# Mỗi write có timestamp
# Khi phát hiện conflict, giữ cái mới nhất

Write A: {user_status: "online",  timestamp: 1000}
Write B: {user_status: "away",    timestamp: 1005}

Phát hiện conflict → So sánh timestamp → Giữ Write B
Trạng thái cuối: user_status = "away"
```

**Vấn đề:** Clock skew có thể gây ra issues
```
Đồng hồ Server A: 10:00:00 (đúng)
Đồng hồ Server B: 09:59:00 (chậm 1 phút)

User cập nhật trên Server A lúc 10:00:00 → timestamp: 1000
User cập nhật trên Server B lúc 10:01:00 → timestamp: 1005 (nhưng đồng hồ hiển thị 1004)

LWW sai lầm ưu tiên write cũ hơn!
```

**2. Version Vectors / Vector Clocks**
```python
# Theo dõi quan hệ nhân quả, không chỉ thời gian

Ban đầu: {value: "hello", version: {A:0, B:0, C:0}}

Server A cập nhật:
{value: "hello world", version: {A:1, B:0, C:0}}

Server B cập nhật (đồng thời):
{value: "hello friend", version: {A:0, B:1, C:0}}

Phát hiện conflict: Không version nào chiếm ưu thế
→ Cả hai version được giữ lại như "siblings"
→ Application giải quyết conflict (hoặc user chọn)
```

**3. CRDTs (Conflict-free Replicated Data Types)**
```python
# Cấu trúc toán học đảm bảo hội tụ

# Ví dụ: G-Counter (Grow-only counter)
class GCounter:
    def __init__(self):
        self.counts = {'A': 0, 'B': 0, 'C': 0}  # Đếm theo từng node
    
    def increment(self, node_id):
        self.counts[node_id] += 1
    
    def value(self):
        return sum(self.counts.values())
    
    def merge(self, other):
        # Lấy max của count mỗi node
        for node_id in self.counts:
            self.counts[node_id] = max(
                self.counts[node_id],
                other.counts[node_id]
            )

# Ngay cả với concurrent updates, merge luôn hội tụ!
```

---

**Khi nào dùng:**
- ✅ Workload nhiều đọc (caching, CDN)
- ✅ Phân tán địa lý (multi-region apps)
- ✅ Yêu cầu high availability (mạng xã hội, content delivery)
- ✅ Ứng dụng offline-first (mobile apps, collaborative docs)

**Khi nào KHÔNG dùng:**
- ❌ Inventory với stock giới hạn
- ❌ Số dư tài khoản ngân hàng
- ❌ Đặt vé (một ghế chỉ bán một lần)
- ❌ Yêu cầu thứ tự nghiêm ngặt

---

**Patterns implementation:**

**Giao thức Gossip:**
```python
# Các node trao đổi state ngẫu nhiên để hội tụ

import random
import time

class GossipNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.data = {}
    
    def gossip(self):
        while True:
            # Chọn peer ngẫu nhiên
            peer = random.choice(self.peers)
            
            # Gửi data của tôi
            peer.receive_gossip(self.data)
            
            # Nhận data của peer
            peer_data = peer.get_data()
            
            # Merge (lấy version mới hơn)
            self.merge(peer_data)
            
            time.sleep(1)  # Gossip mỗi giây
    
    def merge(self, peer_data):
        for key, value in peer_data.items():
            if key not in self.data:
                self.data[key] = value
            elif value['timestamp'] > self.data[key]['timestamp']:
                self.data[key] = value

# Được chứng minh hội tụ: mỗi vòng gossip lan truyền data theo cấp số nhân
# Sau log(N) vòng, tất cả nodes có tất cả data
```

**Read-Your-Writes Consistency:**
```python
# User luôn thấy writes của chính họ (ngay cả khi người khác chưa)

class EventuallyConsistentStore:
    def __init__(self):
        self.primary = {}      # Primary storage
        self.replicas = [{}, {}]  # Replicas nhất quán cuối cùng
        self.user_writes = {}  # Theo dõi user đã write ở đâu
    
    def write(self, user_id, key, value):
        # Ghi vào primary
        self.primary[key] = value
        
        # Theo dõi user này đã write ở đây
        self.user_writes[user_id] = 'primary'
        
        # Async replicate (mô phỏng delay)
        asyncio.create_task(self.replicate(key, value))
        
        return "OK"
    
    def read(self, user_id, key):
        # Nếu user đã write key này, đọc từ primary (write của họ)
        if self.user_writes.get(user_id) == 'primary':
            return self.primary.get(key)
        
        # Nếu không, đọc từ replica ngẫu nhiên (có thể stale)
        replica = random.choice(self.replicas)
        return replica.get(key)
    
    async def replicate(self, key, value):
        await asyncio.sleep(0.5)  # Mô phỏng network delay
        for replica in self.replicas:
            replica[key] = value
```

---

**Trade-offs:**
- ✅ High availability (chấp nhận writes ngay cả khi partition)
- ✅ Độ trễ thấp (không đợi tất cả replicas)
- ✅ Scalable (có thể thêm replicas mà không ảnh hưởng write performance)
- ✅ Partition tolerant
- ❌ Không nhất quán tạm thời (có thể đọc được dữ liệu cũ)
- ❌ Phức tạp trong giải quyết conflict
- ❌ Eventual nghĩa là "không có giới hạn thời gian" (có thể vài giây hoặc vài giờ)
- ❌ Application phải xử lý dữ liệu cũ một cách khéo léo

---

## **Nhất Quán Mạnh (Strong Consistency)**

**Định nghĩa:**
Sau khi một write hoàn thành, **tất cả các lần đọc tiếp theo sẽ thấy write đó hoặc một giá trị mới hơn**. Hệ thống hoạt động như thể chỉ có một bản copy của dữ liệu.

**Đặc điểm chính:**
- Tính tuyến tính (Linearizability): các thao tác xuất hiện tức thời
- Không có stale reads
- Đơn giản để suy luận (như chương trình đơn luồng)
- Availability thấp hơn khi partition

---

**Ví dụ thực tế:**

**1. Hệ thống ngân hàng (số dư tài khoản)**
```
Số dư ban đầu: $1000

Chuỗi giao dịch:
T1: ATM A rút $100 lúc 10:00:00.000
T2: ATM B kiểm tra số dư lúc 10:00:00.001
T3: ATM C rút $50 lúc 10:00:00.002

Với strong consistency:
T1 hoàn thành → Số dư = $900 (TẤT CẢ ATMs thấy $900 ngay lập tức)
T2 đọc → $900 ✓ (thấy write của T1)
T3 hoàn thành → Số dư = $850 (TẤT CẢ ATMs thấy $850 ngay lập tức)

Không ATM nào có thể thấy số dư cũ
Không thể rút quá số dư bằng cách đọc số dư cũ
```

**2. Hệ thống đặt vé của bạn**
```
Địa điểm concert: còn 1 ghế (Ghế A1)

Timeline:
10:00:00.000 - User Alice: GET /seat/A1/status
              Response: "available" ✓

10:00:00.100 - User Alice: POST /book/seat/A1
              Hệ thống khóa ghế
              Xử lý thanh toán
              Commit booking
              Response: "Success" ✓

10:00:00.150 - User Bob: GET /seat/A1/status
              Response: "sold" ✓ (thấy write của Alice ngay lập tức)

10:00:00.200 - User Bob: POST /book/seat/A1
              Response: "Already sold" ✓

Strong consistency ngăn chặn đặt trùng!
```

**3. Trading platform (order book)**
```
Giá cổ phiếu: $100
User đặt: BÁN 10 cổ phiếu @ $102

Order book phải update nguyên tử:
Trước: Best ask = $105
Sau:  Best ask = $102 (TẤT CẢ users thấy điều này ngay lập tức)

Nếu dùng eventual consistency:
  Một số users thấy $102
  Users khác thấy $105
  → Cơ hội arbitrage!
  → Thị trường không công bằng!

Strong consistency đảm bảo: Tất cả traders thấy cùng giá
```

**4. Distributed lock (bầu chọn leader)**
```
5 nodes cần bầu một leader

Với strong consistency (dùng Raft/Paxos):
  Node A đề xuất: "Tôi là leader"
  Đa số (3/5) phải xác nhận
  Khi đã xác nhận: TẤT CẢ nodes biết Node A là leader
  Không có khả năng split-brain (hai leaders)

Với eventual consistency:
  Node A: "Tôi là leader"
  Node B: "Tôi là leader" (chưa biết về A)
  → HAI LEADERS! Hệ thống hỏng ❌
```

---

**Cách implement:**

**1. Synchronous replication**
```python
def write_with_strong_consistency(key, value):
    # Bước 1: Lấy distributed lock
    lock = acquire_lock(key)
    
    try:
        # Bước 2: Ghi vào primary
        primary.write(key, value)
        
        # Bước 3: Replicate tới TẤT CẢ replicas đồng bộ
        for replica in replicas:
            success = replica.write(key, value)
            if not success:
                raise ReplicationError("Replica unavailable")
        
        # Bước 4: Đợi TẤT CẢ xác nhận
        # (Blocking ở đây đảm bảo consistency)
        
        # Bước 5: Commit
        primary.commit(key, value)
        for replica in replicas:
            replica.commit(key, value)
        
        return "Success"
    
    finally:
        # Bước 6: Giải phóng lock
        release_lock(lock)

# Tổng thời gian: Tổng thời gian ghi tất cả replicas
# Độ trễ: Cao
# Nhất quán: Mạnh ✓
```

**2. Giao thức đồng thuận (Raft, Paxos)**
```python
# Đồng thuận Raft cho distributed log

class RaftNode:
    def replicate_log_entry(self, entry):
        # Bước 1: Leader đề xuất entry cho followers
        responses = []
        for follower in self.followers:
            ack = follower.append_entry(entry)
            responses.append(ack)
        
        # Bước 2: Đợi xác nhận từ đa số
        if len([r for r in responses if r.success]) >= (len(self.followers) + 1) // 2:
            # Đa số xác nhận → commit
            self.commit_entry(entry)
            
            # Bước 3: Thông báo followers commit
            for follower in self.followers:
                follower.commit_entry(entry)
            
            return "Committed"
        else:
            # Không đạt đa số → từ chối write
            return "Failed - no quorum"

# Đảm bảo:
# - Khi đã commit, entry sẽ không bao giờ bị mất
# - Tất cả nodes cuối cùng có cùng log (strong consistency)
# - Khi partition: phân vùng thiểu số không thể commit (availability ↓)
```

**3. Two-Phase Commit (2PC)**
```python
# Giao dịch phân tán qua nhiều databases

class TransactionCoordinator:
    def execute_distributed_transaction(self, operations):
        # PHASE 1: CHUẨN BỊ
        prepare_votes = []
        
        for db in databases:
            # Hỏi: "Bạn có thể commit cái này không?"
            vote = db.prepare(operations)
            prepare_votes.append(vote)
        
        # Kiểm tra nếu TẤT CẢ bỏ phiếu YES
        if all(vote == "YES" for vote in prepare_votes):
            # PHASE 2: COMMIT
            for db in databases:
                db.commit()
            return "Transaction committed"
        else:
            # BẤT KỲ ai bỏ phiếu NO → abort trên tất cả
            for db in databases:
                db.abort()
            return "Transaction aborted"

# Ví dụ: Chuyển $100 từ Account A sang Account B
# Database 1: Trừ tiền Account A
# Database 2: Cộng tiền Account B
# 
# Cả hai phải thành công, hoặc cả hai phải thất bại
# Strong consistency: Tất cả DBs có cùng state
```

**4. Quorum reads và writes**
```python
# N = tổng số replicas
# W = write quorum (bao nhiêu phải xác nhận write)
# R = read quorum (phải đọc từ bao nhiêu)
# 
# Strong consistency khi: R + W > N

# Ví dụ: N=5, W=3, R=3
# (3 + 3 = 6 > 5, nên đảm bảo overlap)

def strong_consistent_write(key, value):
    N = 5
    W = 3
    
    acks = 0
    for replica in all_replicas:
        if replica.write(key, value):
            acks += 1
        if acks >= W:
            return "Success"  # Đủ acks rồi
    
    return "Failed"  # Không đạt quorum

def strong_consistent_read(key):
    N = 5
    R = 3
    
    responses = []
    for replica in all_replicas:
        value = replica.read(key)
        responses.append(value)
        if len(responses) >= R:
            break
    
    # Trả về giá trị mới nhất (theo timestamp/version)
    return max(responses, key=lambda x: x.timestamp)

# Vì R + W > N, read quorum PHẢI overlap với write quorum
# Do đó, đọc luôn thấy write mới nhất
```

---

**Khi nào dùng:**
- ✅ Hệ thống tài chính (ngân hàng, thanh toán, trading)
- ✅ Quản lý inventory (stock giới hạn)
- ✅ Hệ thống booking (khách sạn, máy bay, vé)
- ✅ Metadata quan trọng (quyền user, cấu hình)
- ✅ Bầu chọn leader / phối hợp phân tán

**Khi nào KHÔNG dùng:**
- ❌ Yêu cầu high-availability (feed mạng xã hội)
- ❌ Đọc phân tán địa lý (độ trễ quá cao)
- ❌ Ghi throughput cao (synchronous replication chậm)
- ❌ Hệ thống phải hoạt động khi network partition

---

**Trade-offs:**
- ✅ Đơn giản để suy luận (hoạt động như single machine)
- ✅ Không có data conflicts
- ✅ Không có stale reads
- ✅ Đảm bảo tính đúng đắn mạnh mẽ
- ❌ Độ trễ cao hơn (đợi đồng bộ hóa)
- ❌ Availability thấp hơn (không thể phục vụ khi partition)
- ❌ Throughput thấp hơn (synchronous replication bottleneck)
- ❌ Không partition tolerant (CP, không phải AP)
- ❌ Single point of failure (nếu primary down, không có writes)

---

## Tóm tắt Phổ Nhất Quán

```
Weak ←────────── Eventual ←────────── Strong
│                   │                    │
│                   │                    │
Nhanh, Sẵn sàng     Cân bằng            Chậm, Nhất quán
Không đảm bảo       Cuối cùng giống     Luôn giống
VoIP, Gaming        Mạng xã hội         Ngân hàng, Trading
```

**Chọn mô hình consistency phù hợp:**

| Use Case | Mô hình | Tại sao |
|----------|---------|---------|
| Stream video trực tiếp | Weak | Mất frame chấp nhận được, độ trễ thấp quan trọng |
| Feed mạng xã hội | Eventual | Post cũ vài giây OK, cần high availability |
| Catalog e-commerce | Eventual | Thay đổi giá có thể lan truyền chậm |
| Giỏ hàng | Eventual (với read-your-writes) | User thấy thay đổi của họ ngay lập tức |
| Inventory (stock giới hạn) | Strong | Không thể bán quá số lượng |
| Chuyển tiền ngân hàng | Strong | Không thể mất hoặc nhân đôi tiền |
| Đặt vé | Strong | Một ghế chỉ bán một lần |
| Xác thực user | Strong | Bảo mật quan trọng |
| Dashboard metrics | Weak | Dữ liệu gần đúng chấp nhận được |
| DNS | Eventual | High availability > perfect consistency |
| Distributed locks | Strong | Chính xác một lock holder |

---

Bạn muốn tôi tiếp tục với **Availability Patterns** (Fail-over, Replication, Availability in numbers) không?