# TODO – Event Ticket Booking System  
### Async + WebSockets + PostgreSQL + Redis — Scalable to Millions of Users 🚀

---

## 🎯 Project Vision

A real-time ticketing platform that:
- Prevents **overselling** under extreme concurrency
- Supports **world tour level surge** (millions of users)
- Provides **live seat updates** via WebSockets
- Leverages **async I/O** for high performance

Tech Stack Focus:
- Python, FastAPI, asyncio
- PostgreSQL (ACID + row locks)
- Redis (caching + WebSocket fan-out)
- WebSockets (real-time UI)

---

## Phase 1 — Requirements & System Design Basics

- [ ] Create `docs/requirements.md`
  - [ ] Functional requirements
  - [ ] Non-functional requirements (SLA/SLO)
  - [ ] Seat booking workflow diagrams
- [ ] Architecture diagrams:
  - [ ] MVP Single-Node
  - [ ] Scalable Multi-Node (millions of users)
- [ ] Identify bottlenecks + scaling strategies

---

## Phase 2 — Database Schema & Modeling

- [ ] Create `docs/schema.md`
- [ ] Define models:
  - [ ] `users`
  - [ ] `events`
  - [ ] `event_seats`
  - [ ] `bookings`
  - [ ] `booking_seats`
- [ ] Add indexes:
  - [ ] `event_seats(event_id, status)`
  - [ ] `bookings(event_id, status)`
  - [ ] `bookings(hold_expires_at)`
- [ ] Note future scalability options:
  - [ ] Postgres partitioning by event or date

---

## Phase 3 — Backend Boilerplate

- [ ] Initialize project + virtualenv
- [ ] Setup FastAPI app
- [ ] Async DB engine (`asyncpg` + SQLAlchemy)
- [ ] Add `GET /health`
- [ ] Add migrations (Alembic)
- [ ] Seed DB script with:
  - [ ] Sample events
  - [ ] Seats per event (e.g., 500–1000 seats)

---

## Phase 4 — Read-Only APIs

- [ ] `GET /events`
- [ ] `GET /events/{event_id}`
- [ ] `GET /events/{event_id}/seats`
- [ ] Validate resource existence (404 handling)

---

## Phase 5 — Booking Core: ACID Guarantee (No Overselling)

### HOLD booking

- [ ] `POST /bookings`
  - [ ] Validate request (event + seats)
  - [ ] Transaction:
    - [ ] Lock seats with `FOR UPDATE`
    - [ ] Check not BOOKED or HELD
    - [ ] Create booking: `status="HOLD"`
    - [ ] `hold_expires_at = now + 5min`
    - [ ] Create booking-seat rows
    - [ ] Update `current_booking_id`
  - [ ] Commit → return booking

### Confirm booking

- [ ] `POST /bookings/{id}/confirm`
  - [ ] Validate:
    - [ ] booking exists
    - [ ] status == HOLD
    - [ ] not expired
  - [ ] Transaction:
    - [ ] status → CONFIRMED
    - [ ] seats → BOOKED

---

## Phase 6 — Hold Expiration with asyncio Worker

- [ ] Background worker:
  - [ ] Query expired holds
  - [ ] Update booking → EXPIRED
  - [ ] Release seats to AVAILABLE
- [ ] Run using `asyncio.create_task`
- [ ] Verify confirm-after-expire failure works

---

## Phase 7 — WebSockets for Live Seat Map Updates

- [ ] `GET /ws/events/{event_id}/seats`
  - [ ] Track active connections per event
  - [ ] Send initial seat map snapshot
- [ ] Broadcast on:
  - [ ] HOLD
  - [ ] CONFIRMED
  - [ ] EXPIRED
- [ ] JSON payload example:
  ```json
  {
    "type": "seat_update",
    "event_id": 1,
    "seats": [
      {"seat_id": 101, "status": "BOOKED"}
    ]
  }
  ```

---

## Phase 8 — Performance Optimization & Caching

- [ ] Integrate Redis
- [ ] Cache read-heavy endpoints:
  - [ ] Key: `event:{id}:seats`
  - [ ] Falls back to DB if missed
- [ ] On booking updates:
  - [ ] Update DB → invalidate/update Redis → WebSocket broadcast
- [ ] Stateless API → horizontal scaling enabled

---

## Phase 9 — Hot Event Surge Handling

- [ ] Add rate limiting to protect hot endpoints
- [ ] “Waiting Room” mode:
  - [ ] Queue users under peak load
- [ ] Advanced Option (design or implement):
  - [ ] Queue-based booking pipeline (Kafka/Redis Streams)
  - [ ] Idempotency keys for retries
- [ ] Prevent brute force seat probing (anti-bot rules)

---

## Phase 10 — Observability & Concurrency Testing

- [ ] Structured logging (trace booking flows)
- [ ] Metrics:
  - [ ] Booking throughput
  - [ ] WebSocket fan-out latency
  - [ ] Hold expiration performance
- [ ] Load testing:
  - [ ] Thousands of users targeting same seat
  - [ ] Assert: **no double booking**

---

## Phase 11 — Scalability to Millions of Users (Big System Design)

- [ ] Multi-node architecture:
  - [ ] API behind LB
  - [ ] WebSocket servers using Redis Pub/Sub
- [ ] PostgreSQL enhancements:
  - [ ] Read replicas for seat reads
  - [ ] Partition bookings table
- [ ] Fault tolerance:
  - [ ] Redis cluster
  - [ ] Postgres HA (Multi-AZ)
- [ ] Graceful degradation:

￼
￼
￼
Sonnet 4.5
￼

  - [ ] Read-only mode if DB writes lag

📌 Result: Can handle **10M+ simultaneous users** during global ticket drops.

---

## Phase 12 — Documentation + Interview Packaging

- [ ] Fully polished `README.md` with:
  - [ ] Problem statement
  - [ ] Sequence diagram (HOLD → CONFIRM → EXPIRE)
  - [ ] Architecture diagrams: MVP vs scaled
  - [ ] Concurrency & locking explanation
  - [ ] Scaling & surge-handling strategy
- [ ] Include short system design pitch:
  > “I built a highly scalable ticketing system using async I/O,  
  > strong DB consistency, and real-time WebSockets.  
  > It horizontally scales to millions of users  
  > while preventing overselling under extreme concurrency.”

---

## ✔️ Final Completion Checklist

- [ ] Fully working MVP: no overselling
- [ ] Real-time UI capability proven
- [ ] Load testing success captured in README
- [ ] Scaling strategy clearly communicated
- [ ] Ready for portfolio + interviews 🏆

---

## 🌟 Optional Stretch Goals

- [ ] Payment integration (mock or Stripe Sandbox)
- [ ] Analytics dashboard (seat sales, heatmap)
- [ ] Multi-region rollout plan (latency-aware routing)
- [ ] UI: Interactive seat map with live updates