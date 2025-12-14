# Event Ticket Booking System - Requirements

## 1. Functional Requirements

### 1.1 Event Management
- **FR-1.1**: System shall display a list of available events with basic information (name, date, venue, available seats)
- **FR-1.2**: System shall show detailed event information including seat map and pricing
- **FR-1.3**: System shall support multiple pricing tiers per event (VIP, Regular, Economy)

### 1.2 Seat Selection & Booking
- **FR-2.1**: Users shall be able to view real-time seat availability for an event
- **FR-2.2**: Users shall be able to select specific seats from an interactive seat map
- **FR-2.3**: System shall place a temporary hold on selected seats (5-minute expiration)
- **FR-2.4**: Users shall be able to confirm a booking within the hold period
- **FR-2.5**: System shall automatically release seats if not confirmed within hold period
- **FR-2.6**: Users shall receive booking confirmation with unique booking ID

### 1.3 Real-time Updates
- **FR-3.1**: System shall broadcast seat status changes to all active viewers in real-time
- **FR-3.2**: System shall update seat availability immediately when bookings occur
- **FR-3.3**: System shall notify users when their held seats are about to expire (30 seconds warning)

### 1.4 Concurrency & Data Integrity
- **FR-4.1**: System shall prevent double-booking of seats under any concurrency scenario
- **FR-4.2**: System shall handle race conditions when multiple users attempt to book the same seat
- **FR-4.3**: System shall maintain ACID properties for all booking transactions

---

## 2. Non-Functional Requirements

### 2.1 Performance (SLA/SLO)

**Normal Load (< 1000 concurrent users per event):**
- **NFR-1.1**: API response time: P95 < 200ms, P99 < 500ms
- **NFR-1.2**: WebSocket message delivery: < 100ms from event occurrence
- **NFR-1.3**: Database query time: < 50ms for seat availability checks
- **NFR-1.4**: Hold expiration processing: < 1 second from expiry time

**Peak Load (Flash Sales - 100K+ concurrent users):**
- **NFR-1.5**: API response time: P95 < 1s, P99 < 3s
- **NFR-1.6**: System shall maintain availability > 99.9% during surge
- **NFR-1.7**: Queue admission time: < 30 seconds for users during waiting room mode

### 2.2 Scalability
- **NFR-2.1**: System shall support horizontal scaling to handle 10M+ concurrent users
- **NFR-2.2**: System shall handle 100K+ booking requests per second during flash sales
- **NFR-2.3**: WebSocket layer shall support 1M+ simultaneous connections per event
- **NFR-2.4**: Database shall support partitioning for events with 50K+ seats

### 2.3 Reliability & Availability
- **NFR-3.1**: System uptime: 99.99% (52 minutes downtime per year)
- **NFR-3.2**: Zero data loss for confirmed bookings
- **NFR-3.3**: Automatic failover: < 30 seconds
- **NFR-3.4**: Graceful degradation: Read-only mode if write capacity exceeded

### 2.4 Consistency
- **NFR-4.1**: Strong consistency for booking operations (no eventual consistency acceptable)
- **NFR-4.2**: Seat availability must reflect actual state within 100ms
- **NFR-4.3**: Zero tolerance for overselling

### 2.5 Security
- **NFR-5.1**: Rate limiting: 10 booking attempts per user per minute
- **NFR-5.2**: Bot detection and prevention for automated seat grabbing
- **NFR-5.3**: API authentication required for all write operations
- **NFR-5.4**: Input validation to prevent SQL injection and XSS attacks

---

## 3. Seat Booking Workflow

### 3.1 Happy Path Flow
```
User → Select Event → View Seat Map → Select Seats → Hold Created (5 min timer)
  → User Confirms → Payment → Booking Confirmed → Seats Marked BOOKED
  → Email Confirmation Sent
```

**Detailed Steps:**

1. **Event Discovery (0-5s)**
   - User browses events
   - System displays cached event list
   - User clicks event to view details

2. **Seat Selection (5-30s)**
   - WebSocket connection established
   - Real-time seat map loaded
   - User selects desired seats
   - Visual feedback shows seats as "being selected"

3. **Hold Creation (30ms-200ms)**
   - POST /bookings with selected seat IDs
   - Database transaction:
     - FOR UPDATE lock on seats
     - Validate seats are AVAILABLE
     - Create booking record (status=HOLD)
     - Update seats to HOLD status
     - Set hold_expires_at = now + 5min
   - WebSocket broadcast: seats marked as HOLD
   - Return booking ID to user

4. **User Confirmation (0-300s)**
   - User reviews selection
   - Timer displayed: "3:45 remaining"
   - User proceeds to payment
   - POST /bookings/{id}/confirm

5. **Booking Confirmation (50ms-300ms)**
   - Validate booking exists and not expired
   - Mock payment processing
   - Database transaction:
     - Update booking status → CONFIRMED
     - Update seats → BOOKED
   - WebSocket broadcast: seats marked as BOOKED
   - Send confirmation email (async)

### 3.2 Expiration Flow
```
Hold Created → 5 minutes pass → Background Worker Detects Expiry
  → Booking status → EXPIRED → Seats → AVAILABLE
  → WebSocket Broadcast → UI Updates
```

**Background Worker (runs every 10 seconds):**
```python
async def expire_holds():
    while True:
        # Find expired holds
        expired_bookings = await get_expired_holds()
        
        for booking in expired_bookings:
            async with transaction():
                booking.status = EXPIRED
                release_seats(booking.seats)
        
        # Broadcast updates
        await broadcast_seat_updates(expired_bookings)
        
        await asyncio.sleep(10)
```

### 3.3 Race Condition Handling

**Scenario: Two users try to book the same seat simultaneously**
```
User A                          Database                    User B
  |                                 |                          |
  |-- POST /bookings (seat 101) --->|                          |
  |                            [LOCK seat 101]                 |
  |                         [seat.status = AVAILABLE]          |
  |                         [Create booking A]                 |
  |                         [seat.status = HOLD]               |
  |                            [COMMIT]                        |
  |<---- 200 OK (booking_id=A) -----|                          |
  |                                 |<-- POST /bookings (101)--|
  |                            [LOCK seat 101]                 |
  |                         [seat.status = HOLD ❌]            |
  |                         [ROLLBACK]                         |
  |                                 |---- 409 Conflict ------->|
```

**Key Protection Mechanism:**
- PostgreSQL `SELECT ... FOR UPDATE` provides row-level lock
- Transaction isolation level: READ COMMITTED
- Atomic check-and-set operation

---

## 4. Capacity Planning

### 4.1 Normal Event (5,000 seats, 20,000 interested users)

**Assumptions:**
- Event goes on sale at 10:00 AM
- 80% of users access within first 30 minutes
- Average booking: 2.5 seats
- Hold conversion rate: 60%

**Calculations:**
```
Peak concurrent users: 16,000 (80% of 20K)
Booking attempts: 16,000 / 2.5 = 6,400
Successful bookings: 5,000 / 2.5 = 2,000
Failed/expired: 4,400

Requests per second (first minute):
  - Seat map views: 16,000 / 60 = 267 RPS
  - Booking attempts: 6,400 / 60 = 107 RPS
  - WebSocket messages: 267 connections * 10 updates/min = 2,670 msg/min = 45 msg/sec
```

**Resource Requirements:**
- API servers: 2-3 instances (500 RPS capacity each)
- WebSocket servers: 2 instances (10K connections each)
- PostgreSQL: Single instance with 100 connections
- Redis: Single instance for caching

### 4.2 Stadium Event (80,000 seats, 5M interested users - Taylor Swift level)

**Assumptions:**
- Waiting room: admit 50K users per minute
- First 10 minutes: 500K concurrent users
- Average booking: 4 seats
- Hold conversion rate: 40% (many fails due to speed)

**Calculations:**
```
Successful bookings needed: 80,000 / 4 = 20,000
Total booking attempts: 20,000 / 0.4 = 50,000

First 10 minutes:
  - Users admitted: 500K
  - Booking RPS: 50,000 / 600 = 83 RPS (sustained)
  - Peak RPS: 200-300 RPS (bursts)
  - WebSocket messages: 500K connections * 5 updates/min = 42K msg/sec
```

**Resource Requirements:**
- API servers: 20+ instances behind load balancer
- WebSocket servers: 50+ instances (10K connections each)
- PostgreSQL: Primary + 3 read replicas
- Redis: 3-node cluster for caching + pub/sub
- Message queue: Kafka/Redis Streams for booking pipeline

---

## 5. Key System Constraints

### 5.1 Business Rules
- Maximum 10 seats per booking
- Hold duration: 5 minutes (configurable per event)
- Maximum 3 active holds per user at a time
- Refund window: 24 hours before event

### 5.2 Technical Constraints
- Database connection pool: 100 connections per instance
- WebSocket connection limit: 10K per server instance
- Redis memory: 16GB (cache 1M events * 1K seats avg)
- API rate limit: 100 requests/min per user (normal), 10/min during surge

### 5.3 Edge Cases to Handle
- User closes browser during hold → seats auto-released
- Network partition during confirm → idempotency key prevents double charge
- Database failover during transaction → retry with exponential backoff
- Redis cache miss during peak → fallback to DB with circuit breaker
- WebSocket disconnection → automatic reconnection with state sync

---

## 6. Success Metrics

### 6.1 Business Metrics
- Booking conversion rate: > 60%
- Average time to book: < 2 minutes
- Customer satisfaction: > 4.5/5
- Revenue per event: maximize by preventing cart abandonment

### 6.2 Technical Metrics
- Zero overselling incidents
- API uptime: > 99.99%
- P95 latency: < 200ms (normal), < 1s (peak)
- WebSocket delivery success: > 99.9%
- Database deadlock rate: < 0.01%

---

## 7. Out of Scope (for MVP)

- Payment processing (mock only)
- Multi-currency support
- Seat recommendations based on preferences
- Ticket transfers between users
- Mobile native apps
- Email notifications (basic only)
- Analytics dashboard
- Admin panel for event creation