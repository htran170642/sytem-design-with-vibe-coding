# Explain the logic behind handling surge traffic. This is critical for real-world ticketing systems.

---

## 1. Rate Limiter (`rate_limiter.py`)

### **Problem It Solves:**
Prevents users/bots from overwhelming the system with too many requests.

### **How It Works:**

```python
limiter = Limiter(
    key_func=get_identifier,
    default_limits=["100/minute"],
    storage_uri="redis://localhost:6379/1",
    strategy="fixed-window"
)
```

**Key Concepts:**

1. **Identifier Strategy:**
   ```python
   def get_identifier(request: Request) -> str:
       user_id = request.query_params.get('user_id')
       
       if user_id:
           return f"user:{user_id}"  # Rate limit per user
       
       return f"ip:{get_remote_address(request)}"  # Fallback to IP
   ```
   
   - If user is logged in → limit by `user_id` (more accurate)
   - If anonymous → limit by IP address (less accurate, but works)

2. **Fixed Window vs Moving Window:**
   
   **Fixed Window:**
   ```
   Minute 1: [Request 1, 2, 3, ..., 100] ✅
   Minute 2: [Request 1, 2, 3, ..., 100] ✅
   Transition: User could make 200 requests in 2 seconds! ⚠️
   ```
   
   **Moving Window (better):**
   ```
   Always looks at last 60 seconds
   00:00 → 01:00: 100 requests ✅
   00:30 → 01:30: Only counts requests in this window
   ```

3. **Redis Storage:**
   ```
   Redis Key: "LIMITER:user:123"
   Value: {count: 45, expires_at: 1702456789}
   ```
   
   Redis automatically expires keys, cleaning up memory.

### **Real-World Example:**

```
Taylor Swift concert goes on sale:
- User 1: Makes 5 seat requests/second → BLOCKED after 100 requests
- User 2: Makes 1 request every 2 seconds → ✅ Always allowed
```

---

## 2. Waiting Room (`waiting_room.py`)

### **Problem It Solves:**
When 1 million users try to book tickets at the same time, the database crashes. Queue users fairly.

### **How It Works:**

**Architecture:**
```
┌─────────────┐
│ 100K Users  │
│  Arrive     │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Waiting Room    │  ← Only 1,000 users allowed at a time
│ Queue System    │
└──────┬──────────┘
       │
       ▼ (Admitted in batches)
┌─────────────────┐
│ Active Users    │  ← Booking seats
│ (Max 1,000)     │
└─────────────────┘
```

**Data Structures:**

1. **Queue (Redis Sorted Set):**
   ```python
   # Key: waiting_room:1:queue
   # Score = timestamp (FIFO order)
   
   ZADD waiting_room:1:queue 1702456789.123 "token-abc"
   ZADD waiting_room:1:queue 1702456789.456 "token-def"
   ZADD waiting_room:1:queue 1702456789.789 "token-ghi"
   
   # Get position in queue:
   ZRANK waiting_room:1:queue "token-def"  # Returns: 1 (0-indexed)
   ```

2. **Active Sessions (Redis Set):**
   ```python
   # Key: waiting_room:1:active
   # Members = tokens of users currently booking
   
   SADD waiting_room:1:active "token-abc"
   SCARD waiting_room:1:active  # Count active users
   
   # Auto-expire after 5 minutes:
   EXPIRE waiting_room:1:active 300
   ```

### **User Flow:**

```python
# Step 1: User arrives
token = await waiting_room.join_queue(event_id=1, user_id=123)
# Returns: {"token": "abc", "position": 4567, "estimated_wait": 1370}

# Step 2: User polls for status (every 5 seconds)
status = await waiting_room.check_status(event_id=1, token="abc")

# If position > 0:
# {"admitted": False, "position": 4500, "estimated_wait": 1350}

# If position == 0 and slots available:
# {"admitted": True, "message": "You can proceed"}
# → User moved to active set
# → User can now book tickets
```

### **Admission Algorithm:**

```python
async def check_status(event_id, token):
    position = await redis.zrank(queue_key, token)  # Get queue position
    active_count = await redis.scard(active_key)    # Count active users
    max_concurrent = 1000
    
    if active_count < max_concurrent and position == 0:
        # Admit user
        await redis.zrem(queue_key, token)      # Remove from queue
        await redis.sadd(active_key, token)     # Add to active
        return {"admitted": True}
    
    return {"admitted": False, "position": position + 1}
```

### **Why This Works:**

- **Controlled Load:** Only 1,000 concurrent users booking = database doesn't crash
- **Fair:** First-come-first-served (FIFO queue)
- **Transparent:** Users see their position and estimated wait
- **Scalable:** Redis handles millions of queue entries easily

### **Real-World Example:**

```
Ticketmaster waiting room for Beyoncé:
- 2 million users arrive at 10:00 AM
- Max 10,000 active at once
- Queue processes 1,000 users every 30 seconds
- Full queue cleared in ~16 hours
```

---

## 3. Idempotency (`idempotency.py`)

### **Problem It Solves:**
User clicks "Book" button 5 times because page is slow → Creates 5 bookings!

### **How It Works:**

**Idempotency Key Generation:**
```python
# User wants to book seats [1, 2, 3]
params = {
    "event_id": 1,
    "seat_ids": [1, 2, 3]
}

key_data = {
    "user_id": 123,
    "operation": "create_booking",
    "params": sorted(params.items())  # Sort for consistency
}

# Generate hash
hash = SHA256(json.dumps(key_data, sort_keys=True))
# Result: "idempotency:create_booking:a7b3c9d2..."
```

**Request Flow:**

```python
# Request 1: User clicks "Book Seats"
idempotency_key = generate_key(user_id=123, operation="create_booking", 
                                params={"event_id": 1, "seat_ids": [1,2,3]})
# Key: "idempotency:create_booking:a7b3c9"

# Check if already done
existing = await redis.get(idempotency_key)
if existing:
    return existing  # Return cached result (no double booking!)

# Lock operation (prevent concurrent duplicates)
lock_acquired = await redis.set(f"{idempotency_key}:lock", "1", ex=30, nx=True)

if not lock_acquired:
    return {"error": "Operation in progress, please wait"}

# Perform booking
result = await create_booking_in_db(...)

# Store result for 24 hours
await redis.set(idempotency_key, result, ex=86400)

# Release lock
await redis.delete(f"{idempotency_key}:lock")

return result
```

### **Scenario:**

```
User clicks "Book" 5 times rapidly:

Request 1: Key = "abc", Lock acquired, Booking created ✅
Request 2: Key = "abc", Lock exists → "Operation in progress" ⏳
Request 3: Key = "abc", Lock exists → "Operation in progress" ⏳
Request 4: Key = "abc", Result cached → Return cached result ♻️
Request 5: Key = "abc", Result cached → Return cached result ♻️

Result: Only 1 booking created!
```

### **Why Different From Unique Constraints?**

```
Database Unique Constraint:
- Prevents duplicates at DB level
- But still processes request twice (wastes resources)

Idempotency:
- Prevents duplicate REQUESTS (doesn't even hit DB)
- Caches result (instant response on retry)
```

---

## 4. Anti-Bot Protection (`anti_bot.py`)

### **Problem It Solves:**
Bots scan all seats to find best ones before humans can book.

### **Attack Scenarios:**

**Scenario 1: Seat Probing**
```python
# Bot's strategy:
for seat_id in range(1, 10000):
    response = requests.get(f"/events/1/seats")
    # Parse response, find AVAILABLE seats
    # Book only the best seats
```

**Defense:**
```python
# Track seat checks per user
minute_key = "antibot:seat_check:minute:user:123"
count = await redis.incr(minute_key)

if count == 1:
    await redis.expire(minute_key, 60)  # Expire after 1 minute

if count > 10:
    raise HTTPException(429, "Too many seat checks")
```

**Scenario 2: Bulk Booking Bot**
```python
# Bot creates 100 bookings in 1 second
for i in range(100):
    asyncio.create_task(create_booking(event_id=1, seats=[i]))
```

**Defense:**
```python
attempts_key = f"antibot:booking_attempts:hour:{user_id}"
attempts = await redis.incr(attempts_key)

if attempts == 1:
    await redis.expire(attempts_key, 3600)

if attempts > 10:
    raise HTTPException(429, "Too many booking attempts")
```

**Scenario 3: User-Agent Spoofing**
```python
# Bot pretends to be a browser
headers = {"User-Agent": "curl/7.68.0"}
```

**Defense:**
```python
user_agent = request.headers.get("user-agent", "").lower()

bot_patterns = ["bot", "crawler", "curl", "wget", "python-requests"]

for pattern in bot_patterns:
    if pattern in user_agent:
        raise HTTPException(403, "Automated access not allowed")
```

---

## How They Work Together

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  1. Rate Limiter              │
         │  "Max 100 requests/minute"    │
         └──────────┬───────────────────┘
                    │ ✅ Allowed
                    ▼
         ┌──────────────────────────────┐
         │  2. Anti-Bot Check            │
         │  "User-Agent OK?"             │
         │  "Not probing seats?"         │
         └──────────┬───────────────────┘
                    │ ✅ Looks human
                    ▼
         ┌──────────────────────────────┐
         │  3. Waiting Room              │
         │  "Queue if surge traffic"     │
         └──────────┬───────────────────┘
                    │ ✅ Admitted (or queued)
                    ▼
         ┌──────────────────────────────┐
         │  4. Idempotency Check         │
         │  "Already processed?"         │
         └──────────┬───────────────────┘
                    │ ✅ New request
                    ▼
         ┌──────────────────────────────┐
         │  5. Process Booking           │
         │  "Create booking in DB"       │
         └──────────┬───────────────────┘
                    │
                    ▼
              ✅ Success!
```

---

## Real-World Numbers

**Taylor Swift Eras Tour (2023):**
- 3.5 million fans tried to buy tickets
- Ticketmaster's systems crashed
- Queue times: 6-8 hours
- Many fans got error messages

**With Our System:**
```
Waiting Room: 10,000 concurrent users
Queue: 3.5 million users
Processing Rate: 1,000 users/minute
Total Time: ~58 hours to clear queue

But users see:
- Position in queue
- Estimated wait time
- Fair FIFO ordering
- No system crashes
```

---

# TESTING
