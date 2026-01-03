# Phần 2: Các Mẫu Tính Sẵn Sàng - Chỉ Giải Thích

---

## **Replication (Sao chép dữ liệu)**

**Định nghĩa:** Sao chép dữ liệu qua nhiều server để cung cấp tính dự phòng, khả năng chịu lỗi và cải thiện hiệu suất đọc.

---

## **1. Master-Slave Replication (Primary-Replica)**

### **Tổng quan Kiến trúc**

```
                    ┌──────────────┐
           Writes   │    Master    │   Reads
        ────────────►│  (Primary)   │◄────────
                    └───────┬──────┘
                            │
                   Replication (một chiều)
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

### **Cách Hoạt Động**

**Đường đi của Write (Ghi):**
1. Client gửi request ghi dữ liệu
2. **Chỉ có Master** mới có thể chấp nhận writes
3. Master ghi vào local storage của nó
4. Master sao chép tới **tất cả Slaves** (một chiều)
5. Trả về success cho client (thời điểm phụ thuộc vào chế độ replication)

**Đường đi của Read (Đọc):**
1. Client gửi request đọc dữ liệu
2. Có thể đọc từ **Master HOẶC bất kỳ Slave nào**
3. Load balancer phân phối traffic đọc qua tất cả các nodes
4. Giảm tải cho Master (scaling cho đọc)

### **Các Chế Độ Replication**

#### **Asynchronous Replication (Nhất quán cuối cùng)**

**Timeline:**
```
T=0ms:   Client ghi vào Master
T=1ms:   Master lưu locally
T=2ms:   Master trả về "Success" cho client ← NHANH!
T=50ms:  Master sao chép tới Slave-1 (background)
T=150ms: Master sao chép tới Slave-2
T=300ms: Master sao chép tới Slave-3

Từ T=2ms đến T=300ms: Slaves có dữ liệu CŨ (STALE)
Sau T=300ms: Tất cả nhất quán (cuối cùng)
```

**Đặc điểm:**
- ✅ **Ghi nhanh** (~1-2ms) - không đợi slaves
- ✅ **High availability** - hoạt động ngay cả khi slaves down
- ❌ **Eventual consistency** - slaves bị lag sau master
- ❌ **Rủi ro mất dữ liệu** - nếu master crash trước khi replication hoàn thành

**Ví dụ Kịch bản:**
```
User đăng comment trên Facebook:
T=0ms:   Ghi vào Master ở US datacenter
T=1ms:   User thấy "Comment đã đăng!" ✓
T=100ms: Sao chép tới EU datacenter
T=300ms: Sao chép tới Asia datacenter

User ở US: Thấy comment ngay lập tức
User ở EU: Thấy comment sau 100ms
User ở Asia: Thấy comment sau 300ms

Chấp nhận được: Feed mạng xã hội không cần nhất quán toàn cầu ngay lập tức
```

#### **Synchronous Replication (Nhất quán mạnh)**

**Timeline:**
```
T=0ms:   Client ghi vào Master
T=1ms:   Master lưu locally
T=2ms:   Master gửi tới Slave-1 → đợi ACK
T=50ms:  Slave-1 ACK nhận được
T=51ms:  Master gửi tới Slave-2 → đợi ACK
T=150ms: Slave-2 ACK nhận được
T=151ms: Master gửi tới Slave-3 → đợi ACK
T=300ms: Slave-3 ACK nhận được
T=301ms: Master trả về "Success" cho client ← CHẬM nhưng AN TOÀN

Tất cả slaves có dữ liệu TRƯỚC KHI client được thông báo
```

**Đặc điểm:**
- ❌ **Ghi chậm** (~100-300ms) - đợi tất cả slaves
- ✅ **Nhất quán mạnh** - tất cả nodes ngay lập tức nhất quán
- ✅ **Không mất dữ liệu** - slaves có dữ liệu trước khi write trả về
- ❌ **Availability thấp hơn** - write thất bại nếu bất kỳ slave nào down

**Ví dụ Kịch bản:**
```
Chuyển tiền ngân hàng:
User chuyển $1000 từ Tài khoản A sang Tài khoản B

T=0ms:   Ghi vào Master (trừ $1000 từ A)
T=1ms:   Master lưu
T=100ms: Đợi TẤT CẢ slaves sao chép
T=101ms: TẤT CẢ slaves xác nhận đã có giao dịch
T=102ms: Trả về success cho user

Nếu user ngay lập tức kiểm tra số dư ở BẤT KỲ ATM nào (bất kỳ server nào):
→ Tất cả đều hiển thị số dư đúng
→ Không có khả năng thấy số dư cũ
```

#### **Semi-Synchronous Replication (Kết hợp)**

**Cách hoạt động:**
- Đợi **ít nhất MỘT** slave xác nhận (không phải tất cả)
- Các slaves khác sao chép không đồng bộ

**Timeline:**
```
T=0ms:   Ghi vào Master
T=1ms:   Master lưu locally
T=2ms:   Gửi tới cả 3 slaves
T=50ms:  Slave-1 ACK (đầu tiên phản hồi)
T=51ms:  Master trả về "Success" ← Nhanh hơn full sync!
T=150ms: Slave-2 ACK (background)
T=300ms: Slave-3 ACK (background)
```

**Đặc điểm:**
- ✅ **Độ trễ cân bằng** (~50ms) - chỉ đợi một slave
- ✅ **Độ bền tốt** - ít nhất 2 bản copy (master + 1 slave)
- ⚠️ **Nhất quán kết hợp** - tốt hơn async, không mạnh bằng sync
- ✅ **Availability tốt hơn** - chịu được một số slave failures

**Use case:** MySQL's semi-sync replication, PostgreSQL với quorum commits

---

### **Lợi Ích Scaling Đọc**

**Kịch bản: Ứng dụng web với 90% đọc, 10% ghi**

**Không có Slaves (Chỉ Master):**
```
Master xử lý:
- 1,000 writes/sec
- 9,000 reads/sec
Tổng: 10,000 requests/sec

Master CPU: 100% (bottleneck!)
```

**Với 3 Slaves:**
```
Master xử lý:
- 1,000 writes/sec
- 2,250 reads/sec (25% read load)
Tổng: 3,250 requests/sec (Master CPU: 32%)

Mỗi Slave xử lý:
- 2,250 reads/sec
Slave CPU: 22% mỗi cái

Tổng capacity hệ thống: 
- Vẫn 1,000 writes/sec (master bottleneck)
- 9,000 reads/sec được phân phối
- Còn chỗ để grow!
```

**Mẫu scaling:**
```
1 Master + 0 Slaves:  10,000 reads/sec max
1 Master + 3 Slaves:  40,000 reads/sec (cải thiện 4×)
1 Master + 9 Slaves: 100,000 reads/sec (cải thiện 10×)
```

### **Write Bottleneck (Nút thắt ghi)**

**Vấn đề:**
```
Tất cả writes phải đi qua Master
Master có thể xử lý: 10,000 writes/sec

Nếu cần 50,000 writes/sec thì sao?
→ Thêm slaves không giúp được gì (chỉ xử lý reads)
→ Master là bottleneck

Giải pháp:
1. Vertical scaling: Server master lớn hơn (giới hạn, đắt)
2. Sharding: Chia data ra nhiều master-slave clusters
3. Master-Master: Nhiều masters (phức tạp)
```

---

### **Replication Lag (Độ trễ sao chép)**

**Đó là gì:**
Khoảng thời gian delay giữa khi dữ liệu được ghi vào master và khi nó xuất hiện trên slaves.

**Lag điển hình:**
```
Cùng datacenter:     10-100ms
Cross-region:        100-500ms
Xuyên lục địa:       200-1000ms
```

**Vấn đề do lag gây ra:**

**1. Vi phạm Read-Your-Writes Consistency:**
```
User đăng một tweet:
T=0ms:   Ghi vào Master (US-East)
T=1ms:   User được redirect tới trang profile
T=2ms:   Trang profile đọc từ Slave (US-West)
         Slave chưa nhận được replication!
         User: "Tweet của tôi đâu rồi?!" ❌
```

**Giải pháp:**
```
Sau khi write, tạm thời đọc từ Master cho user đó:
T=0ms:   Ghi vào Master
T=1ms:   Lưu session: "read_from_master_until = T + 5 giây"
T=2ms:   Trang profile check session → đọc từ Master
T=2ms:   User thấy tweet của họ ✓
T=5s:    Session hết hạn → có thể đọc từ Slave lại
```

**2. Quay Ngược Thời Gian:**
```
User refresh trang hai lần:
Refresh 1: Load balanced tới Slave-A (replication lag: 100ms)
           Thấy 100 tweets

Refresh 2: Load balanced tới Slave-B (replication lag: 500ms)
           Thấy 95 tweets (state cũ hơn!)
           
User: "Tôi mất 5 tweets à?!" ❌
```

**Giải pháp:**
```
Monotonic reads: Gắn user vào cùng một slave
- Dùng sticky sessions (cookie)
- Hoặc: Include timestamp trong reads, chỉ hiển thị data mới hơn lần thấy cuối
```

**3. Vi phạm Quan hệ Nhân quả:**
```
Alice đăng: "Bob là người chiến thắng!"
Bob trả lời: "Cảm ơn Alice!"

Timeline:
T=0:   Post của Alice ghi vào Master
T=1:   Master sao chép tới Slave-A
T=2:   Bob đọc từ Slave-A, thấy post của Alice
T=3:   Reply của Bob ghi vào Master
T=4:   Master sao chép tới Slave-B (nhưng post của Alice chưa tới đó!)

User đọc từ Slave-B thấy:
  Bob: "Cảm ơn Alice!"
  (Post của Alice đâu rồi?!) ❌
```

**Giải pháp:**
```
Consistent prefix reads: Đảm bảo các writes liên quan xuất hiện theo thứ tự
- Dùng version vectors
- Hoặc: Đọc từ Master cho dependent reads
```

---

### **Slave Promotion (Failover)**

**Khi Master fail, thăng cấp một Slave thành Master mới:**

**Quy trình:**
```
1. Phát hiện Master failure (30-60 giây)
   - Heartbeat timeout
   - Kiểm tra xác nhận nhiều lần

2. Chọn Slave nào để thăng cấp (10-20 giây)
   - Ưu tiên slave có replication lag thấp nhất
   - Kiểm tra tính nhất quán dữ liệu
   
3. Thăng cấp Slave (20-40 giây)
   - Dừng replication trên slave được chọn
   - Làm cho nó writable (thay đổi config)
   - Cập nhật DNS/load balancer
   
4. Cập nhật các Slaves khác (10-30 giây)
   - Chỉ chúng tới Master mới
   - Bắt đầu replicate từ Master mới
   
Tổng: 70-150 giây downtime
```

**Rủi Ro Mất Dữ Liệu:**

**Kịch bản:**
```
T=0:     Master nhận write: "order_id=999"
T=1:     Master lưu locally
T=2:     Master bắt đầu async replication
T=3:     Master CRASH! 💥
         (Trước khi replication hoàn thành)

T=60:    Slave được thăng cấp thành Master mới
         Slave không có order_id=999
         
Kết quả: Order bị mất! ❌
```

**Cách giảm thiểu:**
```
1. Dùng synchronous replication (đợi ít nhất 1 slave)
2. Dùng semi-sync (cân bằng tốc độ vs an toàn)
3. Ship WAL (Write-Ahead Log) thường xuyên
4. Có monitoring để phát hiện và cảnh báo về lag
```

---

## **2. Master-Master Replication (Multi-Master)**

### **Tổng quan Kiến trúc**

```
           ┌──────────────┐
    Writes │   Master A   │ Writes
 ─────────►│              │◄─────────
    Reads  │              │  Reads
           └──────┬───────┘
                  │
         Bidirectional Sync
         (Cả hai chiều)
                  │
           ┌──────┴───────┐
    Writes │   Master B   │ Writes
 ─────────►│              │◄─────────
    Reads  │              │  Reads
           └──────────────┘
```

### **Cách Hoạt Động**

**Cả hai masters có thể:**
- Chấp nhận writes
- Chấp nhận reads
- Sao chép cho nhau (hai chiều)

**Timeline:**
```
T=0:   User ở US ghi vào Master-A
T=1:   Master-A lưu locally
T=2:   Master-A trả về success
T=50:  Master-A sao chép tới Master-B (async)

T=100: User ở EU ghi vào Master-B
T=101: Master-B lưu locally
T=102: Master-B trả về success
T=150: Master-B sao chép tới Master-A (async)

Cả hai masters hoạt động đồng thời
```

### **Use Cases**

**1. Thiết lập Multi-Region:**
```
Users ở US → Master-US (độ trễ thấp: 10ms)
Users ở EU → Master-EU (độ trễ thấp: 10ms)

vs Master-Slave:
Users ở US → Master-US (10ms)
Users ở EU → Master-US (150ms - chậm!)
```

**2. High Availability:**
```
Cả hai masters active:
- Nếu Master-A fail → traffic chuyển sang Master-B (tức thì!)
- Không cần promotion (đã chấp nhận writes sẵn)
- Zero failover time
```

**3. Phân Phối Load:**
```
Cần 10,000 writes/sec
Master-Slave: Tất cả 10,000 qua một master (bottleneck!)
Master-Master: 5,000 mỗi cái (phân phối!)
```

---

### **Vấn Đề Conflict**

**Thách thức quan trọng nhất trong Master-Master replication**

**Kịch bản: Concurrent Writes**

```
Cùng key được ghi trên cả hai masters đồng thời:

T=0:   User A (US) → Master-A: UPDATE account SET status='active'
T=0:   User B (EU) → Master-B: UPDATE account SET status='suspended'

T=1:   Cả hai masters lưu locally
       Master-A có: status='active'
       Master-B có: status='suspended'

T=100: Replication xảy ra
       Master-A nhận: status='suspended' (từ B)
       Master-B nhận: status='active' (từ A)
       
       CONFLICT! Giá trị nào đúng?
```

**Không có conflict resolution:**
```
Masters có thể kết thúc ở trạng thái không nhất quán:
Master-A: status='active'
Master-B: status='suspended'

Users khác nhau thấy data khác nhau!
Hệ thống hỏng! ❌
```

---

### **Chiến Lược Giải Quyết Conflict**

#### **1. Last-Write-Wins (LWW)**

**Cách hoạt động:**
- Gắn timestamp vào mỗi write
- Khi phát hiện conflict, giữ write có timestamp mới nhất
- Loại bỏ write cũ hơn

**Ví dụ:**
```
Master-A: status='active'   (timestamp: 1000.000)
Master-B: status='suspended' (timestamp: 1000.050)

So sánh timestamps: 1000.050 > 1000.000
→ Giữ 'suspended'
→ Loại bỏ 'active'

Cả hai masters hội tụ về: status='suspended'
```

**Vấn đề:**
```
1. Clock skew (đồng hồ lệch):
   Đồng hồ Master-A: 10:00:00
   Đồng hồ Master-B: 10:01:00 (nhanh hơn 1 phút)
   
   T=10:00:00: Master-A ghi (timestamp: 1000)
   T=10:00:30: Master-B ghi (timestamp: 1060 - sai!)
   
   LWW sai lầm chọn Master-B (write cũ hơn!)

2. Mất dữ liệu:
   Write của User A bị loại bỏ âm thầm
   Không có thông báo rằng thay đổi của họ bị mất
```

**Khi nào chấp nhận được:**
- Dữ liệu không quan trọng (cache, session data)
- Khi "bất kỳ giá trị nào" tốt hơn "không có giá trị"
- Giỏ hàng (mất một item tốt hơn giỏ hàng fail)

#### **2. Version Vectors (Theo dõi Quan hệ Nhân quả)**

**Cách hoạt động:**
- Mỗi write có version vector: `{Master-A: 5, Master-B: 3}`
- Theo dõi mỗi master đã ghi bao nhiêu lần vào key này
- Có thể phát hiện writes có đồng thời hay có quan hệ nhân quả

**Ví dụ:**
```
Ban đầu: version={A:0, B:0}

Master-A ghi: version={A:1, B:0}
Master-B ghi: version={A:0, B:1}

Khi sync:
Master-A nhận version={A:0, B:1}
  So sánh: {A:1, B:0} vs {A:0, B:1}
  Không bên nào chiếm ưu thế → CONCURRENT CONFLICT!
  
Master-B nhận version={A:1, B:0}
  So sánh: {A:0, B:1} vs {A:1, B:0}
  Không bên nào chiếm ưu thế → CONCURRENT CONFLICT!

Cả hai phát hiện conflict
→ Có thể dùng application logic để giải quyết
→ Hoặc giữ cả hai như "siblings" để user chọn
```

**Lợi ích:**
- Phát hiện conflicts thật sự (không phải false positives từ clock skew)
- Có thể xác định quan hệ nhân quả (A xảy ra trước B không?)
- Chính xác hơn timestamps

**Nhược điểm:**
- Phức tạp hơn để implement
- Yêu cầu application xử lý conflicts
- Overhead lưu trữ (version vector cho mỗi key)

#### **3. CRDTs (Conflict-Free Replicated Data Types)**

**Cách hoạt động:**
- Cấu trúc dữ liệu đặc biệt đảm bảo toán học là sẽ hội tụ
- Merging là commutative, associative, idempotent
- Không thể có conflicts!

**Ví dụ: G-Counter (Grow-only counter)**
```
Cấu trúc:
{
  Master-A: 5,  // Master-A tăng 5 lần
  Master-B: 3   // Master-B tăng 3 lần
}

Giá trị = sum(all counts) = 5 + 3 = 8

Concurrent increments:
Master-A: tăng → {A:6, B:3}
Master-B: tăng → {A:5, B:4}

Khi merge:
{A: max(6,5), B: max(3,4)} = {A:6, B:4}
Giá trị = 6 + 4 = 10 ✓

Cả hai tự động hội tụ về cùng giá trị!
```

**Lợi ích:**
- Zero conflicts
- Tự động hội tụ
- Đơn giản để suy luận

**Nhược điểm:**
- Giới hạn kiểu dữ liệu (counters, sets, maps)
- Không thể làm các operations tùy ý
- Overhead memory nhiều hơn

#### **4. Application-Level Resolution (Giải quyết cấp Application)**

**Cách hoạt động:**
- Phát hiện conflict
- Giữ cả hai versions
- Application (hoặc user) quyết định

**Ví dụ: Google Docs**
```
User A gõ: "Hello world"
User B gõ: "Goodbye world" (đồng thời)

Hệ thống phát hiện conflict:
→ Giữ cả hai versions như branches
→ Hiển thị cho user: "Phát hiện conflict, chọn version nào?"
   [ ] Hello world
   [ ] Goodbye world
   [ ] Merge cả hai

User chọn hoặc merge thủ công
```

**Lợi ích:**
- Linh hoạt (có thể implement bất kỳ logic nào)
- User có quyền kiểm soát
- Không mất dữ liệu

**Nhược điểm:**
- Yêu cầu can thiệp của user
- UI phức tạp
- Không phải lúc nào cũng khả thi (vd: hệ thống tự động)

---

### **Khi Nào Dùng Master-Master**

✅ **Phù hợp:**
- Triển khai multi-region (độ trễ thấp ở mọi nơi)
- Cần throughput ghi cao (phân phối writes)
- Yêu cầu zero downtime (cả hai luôn active)
- Conflicts hiếm hoặc dễ giải quyết

❌ **Không phù hợp:**
- Giao dịch tài chính (conflicts không chấp nhận được)
- Hệ thống inventory (không thể bán quá số lượng)
- Operations tuần tự (thứ tự quan trọng)
- Triển khai đơn giản (overhead không đáng)

---

### **Ví Dụ Thực Tế**

**Master-Master (Multi-Master):**
- **MySQL Group Replication** - nhiều writable masters
- **PostgreSQL BDR** (Bi-Directional Replication)
- **CockroachDB** - distributed SQL với multi-master
- **Cassandra** - mọi node đều là master (masterless)
- **DynamoDB** - multi-region với conflict resolution
- **Riak** - eventually consistent multi-master

**Master-Slave:**
- **MySQL với replicas** - setup phổ biến nhất
- **PostgreSQL với streaming replication**
- **MongoDB replica sets** - 1 primary, N secondaries
- **Redis replication** - chế độ master-slave
- **Elasticsearch** - primary-replica shards

---

## **So Sánh Tổng Kết**

| Khía cạnh | Master-Slave | Master-Master |
|--------|--------------|---------------|
| **Write path** | Tất cả writes → 1 master | Writes → bất kỳ master nào |
| **Write scalability** | Giới hạn (single bottleneck) | Tốt hơn (phân phối) |
| **Read scalability** | Xuất sắc (thêm slaves) | Tốt (cả hai đọc được) |
| **Consistency** | Dễ hơn (một writer) | Phức tạp (conflicts!) |
| **Conflict resolution** | Không cần | Yêu cầu quan trọng |
| **Failover time** | 30-120 giây (thăng cấp slave) | 0 giây (đã active sẵn) |
| **Complexity** | Thấp | Cao |
| **Rủi ro mất dữ liệu** | Có (nếu async) | Có + conflicts |
| **Latency (writes)** | Tốt (1 vị trí master) | Xuất sắc (ghi ở đâu cũng được) |
| **Use case** | Hầu hết databases | Multi-region, high availability |

---

Bạn muốn tôi tiếp tục với **Availability in Numbers** không?