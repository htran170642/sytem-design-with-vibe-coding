# TODO — Road to Master System Design

This plan follows the System Design Primer index and turns it into a structured learning and practice roadmap.

---

## Phase 0 — Orientation

- [ ] Read: System design topics: start here
- [ ] Watch: Scalability video lecture
- [ ] Read: Scalability article
- [ ] Read: Next steps
- [ ] Write a short note: What is system design? What does "scaling" mean?

---

## Phase 1 — Core Trade-offs

- [ ] Read: Performance vs scalability
- [ ] Read: Latency vs throughput
- [ ] Read: Availability vs consistency
- [ ] Read: CAP theorem
- [ ] Read: CP — consistency and partition tolerance
- [ ] Read: AP — availability and partition tolerance
- [ ] Practice: Explain CP vs AP using a banking system and a chat system

---

## Phase 2 — Consistency & Availability

### Consistency Patterns
- [ ] Read: Weak consistency
- [ ] Read: Eventual consistency
- [ ] Read: Strong consistency

### Availability Patterns
- [ ] Read: Fail-over
- [ ] Read: Replication
- [ ] Read: Availability in numbers
- [ ] Practice: Draw read/write timelines and failure scenarios

---

## Phase 3 — Traffic & Edge

- [ ] Read: Domain name system
- [ ] Read: Content delivery network
  - [ ] Push CDNs
  - [ ] Pull CDNs
- [ ] Read: Load balancer
  - [ ] Active-passive
  - [ ] Active-active
  - [ ] Layer 4 load balancing
  - [ ] Layer 7 load balancing
- [ ] Read: Horizontal scaling
- [ ] Read: Reverse proxy (web server)
- [ ] Read: Load balancer vs reverse proxy
- [ ] Practice: Explain request flow from user → DNS → CDN → LB → service

---

## Phase 4 — Application Architecture

- [ ] Read: Application layer
- [ ] Read: Microservices
- [ ] Read: Service discovery
- [ ] Practice: Design monolith → microservices migration

---

## Phase 5 — Data Layer

### Relational
- [ ] Read: RDBMS
- [ ] Read: Master-slave replication
- [ ] Read: Master-master replication
- [ ] Read: Federation
- [ ] Read: Sharding
- [ ] Read: Denormalization
- [ ] Read: SQL tuning

### NoSQL
- [ ] Read: NoSQL
- [ ] Read: Key-value store
- [ ] Read: Document store
- [ ] Read: Wide column store
- [ ] Read: Graph database
- [ ] Read: SQL or NoSQL

- [ ] Practice: Design database for social network or logging system

---

## Phase 6 — Caching

- [ ] Read: Cache overview
- [ ] Read: Client caching
- [ ] Read: CDN caching
- [ ] Read: Web server caching
- [ ] Read: Database caching
- [ ] Read: Application caching
- [ ] Read: Query-level caching
- [ ] Read: Object-level caching

### Cache Update Strategies
- [ ] Read: When to update the cache
- [ ] Read: Cache-aside
- [ ] Read: Write-through
- [ ] Read: Write-behind
- [ ] Read: Refresh-ahead
- [ ] Practice: Draw read/write flows and stale data risks

---

## Phase 7 — Asynchrony & Messaging

- [ ] Read: Asynchronism
- [ ] Read: Message queues
- [ ] Read: Task queues
- [ ] Read: Back pressure
- [ ] Practice: Compare Kafka vs RabbitMQ vs Redis queues

---

## Phase 8 — Communication

- [ ] Read: TCP
- [ ] Read: UDP
- [ ] Read: RPC
- [ ] Read: REST
- [ ] Practice: When to use gRPC vs REST, TCP vs UDP

---

## Phase 9 — Security & Reliability

- [ ] Read: Security
- [ ] Read: Latency numbers every programmer should know
- [ ] Review: Availability in numbers again
- [ ] Practice: Identify bottlenecks and failure points in a sample system

---

## Phase 10 — System Design Practice

- [ ] Review: Additional system design interview questions
- [ ] Review: Real world architectures
- [ ] Review: Company architectures
- [ ] Read: Company engineering blogs

### Full System Designs
- [ ] Design: Ticket booking system (millions of users)
- [ ] Design: Real-time fraud detection system
- [ ] Design: Chat system
- [ ] Design: Video streaming platform

---

## Final Checklist

- [ ] Can explain trade-offs clearly
- [ ] Can design a system end-to-end
- [ ] Can justify every architectural decision
- [ ] Can adapt design based on constraints

---

🎯 Goal: Become fluent in designing scalable, reliable, and maintainable distributed systems.
