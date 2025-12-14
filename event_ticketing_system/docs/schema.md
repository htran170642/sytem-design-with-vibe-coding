# Database Schema - Event Ticket Booking System

## Overview

This document describes the PostgreSQL database schema designed to handle high-concurrency ticket bookings with zero overselling tolerance.

**Key Design Principles:**
- Strong ACID guarantees for booking transactions
- Row-level locking to prevent race conditions
- Optimized indexes for high-read scenarios
- Future-proof for horizontal partitioning

---

## Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│   users     │         │   events     │         │  event_seats    │
├─────────────┤         ├──────────────┤         ├─────────────────┤
│ id (PK)     │         │ id (PK)      │         │ id (PK)         │
│ email       │         │ name         │    ┌────│ event_id (FK)   │
│ full_name   │         │ description  │    │    │ section         │
│ created_at  │         │ venue        │    │    │ row_number      │
└─────────────┘         │ start_time   │    │    │ seat_number     │
                        │ total_seats  │    │    │ price           │
                        │ created_at   │    │    │ status          │
                        └──────┬───────┘    │    │ current_booking │
                               │            │    │ version         │
                               └────────────┘    │ created_at      │
                                                 └────────┬────────┘
                                                          │
┌─────────────┐         ┌──────────────┐                 │
│  bookings   │         │booking_seats │                 │
├─────────────┤         ├──────────────┤                 │
│ id (PK)     │────┐    │ id (PK)      │                 │
│ user_id (FK)│    └────│ booking_id   │                 │
│ event_id    │         │ seat_id (FK) │─────────────────┘
│ status      │         │ created_at   │
│ total_amount│         └──────────────┘
│ hold_expires│
│ created_at  │
│ confirmed_at│
└─────────────┘
```

---

## Table Definitions

### 1. `users` Table

Stores user account information.

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `email`: Unique email address for authentication
- `full_name`: User's display name
- `password_hash`: Bcrypt hashed password
- `created_at`: Account creation timestamp
- `updated_at`: Last modification timestamp

**Notes:**
- Future: Add `phone_number`, `is_verified`, `stripe_customer_id`

---

### 2. `events` Table

Stores event information.

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    venue VARCHAR(500) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_seats INTEGER NOT NULL DEFAULT 0,
    available_seats INTEGER NOT NULL DEFAULT 0,
    category VARCHAR(100),  -- 'concert', 'sports', 'theater', etc.
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_start_time ON events(start_time);
CREATE INDEX idx_events_city_category ON events(city, category);
CREATE INDEX idx_events_is_active ON events(is_active) WHERE is_active = TRUE;
```

**Fields:**
- `id`: Auto-incrementing primary key
- `name`: Event name (e.g., "Taylor Swift - Eras Tour")
- `description`: Event details
- `venue`: Venue name (e.g., "Madison Square Garden")
- `city`, `country`: Location for filtering
- `start_time`: Event start timestamp
- `end_time`: Event end timestamp (optional)
- `total_seats`: Total capacity (denormalized for quick access)
- `available_seats`: **Denormalized counter** - updated via triggers or application logic
- `category`: Event type for filtering
- `is_active`: Soft delete flag

**Design Decisions:**
- `available_seats` is denormalized to avoid expensive COUNT queries
- Partial index on `is_active` for active events listing
- Composite index on `(city, category)` for common search patterns

**Future Scaling:**
- Partition by `start_time` for archiving old events
- Add `event_series_id` for tour events

---

### 3. `event_seats` Table

Stores individual seats with their current status.

**This is the critical table for concurrency control.**

```sql
CREATE TYPE seat_status AS ENUM ('AVAILABLE', 'HOLD', 'BOOKED');

CREATE TABLE event_seats (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    section VARCHAR(50) NOT NULL,      -- 'VIP', 'A', 'B', 'General'
    row_number VARCHAR(10) NOT NULL,   -- 'A', '1', '15'
    seat_number VARCHAR(10) NOT NULL,  -- '1', '12', '101'
    price DECIMAL(10, 2) NOT NULL,
    status seat_status NOT NULL DEFAULT 'AVAILABLE',
    current_booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL,
    version INTEGER NOT NULL DEFAULT 0,  -- Optimistic locking version
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(event_id, section, row_number, seat_number)
);

-- CRITICAL INDEX for seat locking performance
CREATE INDEX idx_event_seats_event_status ON event_seats(event_id, status);

-- Index for finding seats by booking
CREATE INDEX idx_event_seats_booking ON event_seats(current_booking_id) WHERE current_booking_id IS NOT NULL;

-- Index for seat map queries
CREATE INDEX idx_event_seats_section ON event_seats(event_id, section);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `event_id`: Foreign key to events table
- `section`: Seating section (e.g., VIP, Orchestra, Balcony)
- `row_number`: Row identifier (can be letter or number)
- `seat_number`: Seat identifier within the row
- `price`: Seat price (can vary by section)
- `status`: **CRITICAL** - Current seat state (AVAILABLE, HOLD, BOOKED)
- `current_booking_id`: Links to active booking (NULL when AVAILABLE)
- `version`: For optimistic locking (alternative to pessimistic locking)
- `created_at`: Seat creation timestamp
- `updated_at`: Last status change timestamp

**Design Decisions:**
- UNIQUE constraint on `(event_id, section, row_number, seat_number)` prevents duplicates
- `status` ENUM for type safety
- `current_booking_id` makes it easy to find all seats in a booking
- Partial index on `current_booking_id IS NOT NULL` saves space

**Concurrency Strategy:**
```sql
-- Example: Pessimistic locking (primary approach)
SELECT * FROM event_seats 
WHERE id IN (101, 102, 103) 
  AND status = 'AVAILABLE'
FOR UPDATE NOWAIT;  -- Fails immediately if locked

-- Alternative: Optimistic locking using version
UPDATE event_seats 
SET status = 'HOLD', version = version + 1 
WHERE id = 101 
  AND status = 'AVAILABLE' 
  AND version = 5;  -- Must match current version
```

**Future Scaling:**
- Partition by `event_id` for events with 50K+ seats
- Archive old event seats after event ends + 30 days

---

### 4. `bookings` Table

Stores booking records with hold/confirmation status.

```sql
CREATE TYPE booking_status AS ENUM ('HOLD', 'CONFIRMED', 'EXPIRED', 'CANCELLED');

CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    status booking_status NOT NULL DEFAULT 'HOLD',
    total_amount DECIMAL(10, 2) NOT NULL,
    hold_expires_at TIMESTAMP,  -- NULL if CONFIRMED
    payment_id VARCHAR(255),    -- Stripe payment intent ID
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    cancelled_at TIMESTAMP
);

-- CRITICAL INDEX for expiry worker
CREATE INDEX idx_bookings_hold_expires ON bookings(hold_expires_at) 
WHERE status = 'HOLD' AND hold_expires_at IS NOT NULL;

-- Index for user's booking history
CREATE INDEX idx_bookings_user_status ON bookings(user_id, status);

-- Index for event bookings
CREATE INDEX idx_bookings_event ON bookings(event_id);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table
- `event_id`: Foreign key to events table
- `status`: Current booking state (HOLD → CONFIRMED or EXPIRED)
- `total_amount`: Sum of all seat prices
- `hold_expires_at`: **CRITICAL** - Timestamp when hold expires (5 minutes from creation)
- `payment_id`: External payment reference
- `created_at`: Booking creation timestamp
- `confirmed_at`: Payment confirmation timestamp
- `cancelled_at`: Cancellation timestamp

**State Transitions:**
```
HOLD ──(confirm within 5 min)──> CONFIRMED
  │
  └──(expires after 5 min)──────> EXPIRED
  │
  └──(user cancels)─────────────> CANCELLED
```

**Design Decisions:**
- Partial index on `hold_expires_at` for efficient background worker queries
- `status = 'HOLD'` condition in index saves 80% space (most bookings get confirmed)
- Separate timestamps for `created_at`, `confirmed_at`, `cancelled_at` for analytics

**Critical Query (Background Worker):**
```sql
-- Find all expired holds (runs every 10 seconds)
SELECT id, event_id 
FROM bookings 
WHERE status = 'HOLD' 
  AND hold_expires_at < NOW();
```

---

### 5. `booking_seats` Table

Junction table linking bookings to seats.

```sql
CREATE TABLE booking_seats (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    seat_id INTEGER NOT NULL REFERENCES event_seats(id) ON DELETE CASCADE,
    price_at_booking DECIMAL(10, 2) NOT NULL,  -- Snapshot price
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(booking_id, seat_id)
);

CREATE INDEX idx_booking_seats_booking ON booking_seats(booking_id);
CREATE INDEX idx_booking_seats_seat ON booking_seats(seat_id);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `booking_id`: Foreign key to bookings table
- `seat_id`: Foreign key to event_seats table
- `price_at_booking`: Historical price (in case seat price changes)
- `created_at`: Record creation timestamp

**Design Decisions:**
- UNIQUE constraint on `(booking_id, seat_id)` prevents duplicate seat assignments
- `price_at_booking` preserves original price even if event pricing changes
- CASCADE deletes ensure orphaned records don't accumulate

**Common Query:**
```sql
-- Get all seats for a booking
SELECT es.* 
FROM event_seats es
JOIN booking_seats bs ON es.id = bs.seat_id
WHERE bs.booking_id = 123;
```

---

## Sample Data Size Calculations

### Small Event (Concert - 5,000 seats)

```
events: 1 row
event_seats: 5,000 rows
bookings: ~2,000 rows (assuming 60% conversion)
booking_seats: ~5,000 rows (2.5 seats per booking avg)

Total: ~12,001 rows
Estimated size: ~2 MB
```

### Large Event (Stadium - 80,000 seats)

```
events: 1 row
event_seats: 80,000 rows
bookings: ~32,000 rows
booking_seats: ~80,000 rows

Total: ~192,001 rows
Estimated size: ~35 MB
```

### Platform with 1,000 events

```
events: 1,000 rows
event_seats: 10,000,000 rows (avg 10K seats per event)
bookings: 4,000,000 rows
booking_seats: 10,000,000 rows

Total: ~24,001,000 rows
Estimated size: ~4-5 GB (with indexes ~8-10 GB)
```

---

## Database Triggers (Optional but Recommended)

### Trigger: Update `available_seats` counter

```sql
-- Automatically update event.available_seats when seat status changes
CREATE OR REPLACE FUNCTION update_available_seats()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'AVAILABLE' AND NEW.status != 'AVAILABLE' THEN
        -- Seat was taken
        UPDATE events 
        SET available_seats = available_seats - 1 
        WHERE id = NEW.event_id;
    ELSIF OLD.status != 'AVAILABLE' AND NEW.status = 'AVAILABLE' THEN
        -- Seat was released
        UPDATE events 
        SET available_seats = available_seats + 1 
        WHERE id = NEW.event_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_available_seats
AFTER UPDATE OF status ON event_seats
FOR EACH ROW
EXECUTE FUNCTION update_available_seats();
```

**Note:** This trigger adds some overhead, so for ultra-high performance scenarios, you might update `available_seats` manually in the application layer.

---

## Future Scaling Strategies

### 1. Partitioning `event_seats` by `event_id`

For platforms with 100K+ events:

```sql
CREATE TABLE event_seats_partitioned (
    LIKE event_seats INCLUDING ALL
) PARTITION BY HASH (event_id);

CREATE TABLE event_seats_p0 PARTITION OF event_seats_partitioned
    FOR VALUES WITH (MODULUS 10, REMAINDER 0);
-- ... create partitions p1 through p9
```

### 2. Partitioning `bookings` by `created_at`

For archiving old bookings:

```sql
CREATE TABLE bookings_partitioned (
    LIKE bookings INCLUDING ALL
) PARTITION BY RANGE (created_at);

CREATE TABLE bookings_2024_q1 PARTITION OF bookings_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
-- ... create quarterly partitions
```

### 3. Read Replicas

- **Primary**: All writes (bookings, confirmations)
- **Replica 1**: Event listings, seat map reads
- **Replica 2**: User booking history, analytics

### 4. Connection Pooling

Recommended settings:
```
max_connections = 200
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 50MB
```

---

## Schema Evolution Plan

### Version 1.1 (Add waiting list support)

```sql
CREATE TABLE waitlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    section_preference VARCHAR(50),
    max_price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW(),
    notified_at TIMESTAMP,
    UNIQUE(user_id, event_id)
);
```

### Version 1.2 (Add dynamic pricing)

```sql
ALTER TABLE event_seats ADD COLUMN base_price DECIMAL(10, 2);
ALTER TABLE event_seats ADD COLUMN dynamic_multiplier DECIMAL(3, 2) DEFAULT 1.0;

-- price = base_price * dynamic_multiplier
```

### Version 1.3 (Add seat recommendations)

```sql
CREATE TABLE seat_views (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    section VARCHAR(50),
    view_quality_score INTEGER CHECK (view_quality_score BETWEEN 1 AND 10),
    distance_to_stage_meters DECIMAL(5, 2)
);
```

---

## Backup & Recovery Strategy

### Daily Backups
```bash
pg_dump -Fc ticketing_db > backup_$(date +%Y%m%d).dump
```

### Point-in-Time Recovery (PITR)
- Enable WAL archiving
- Retain 7 days of WAL logs
- Test recovery monthly

### Replication
- Synchronous replication for primary-standby
- Asynchronous replication for read replicas

---

## Summary

This schema is designed for:
- ✅ **Zero overselling** via row-level locking
- ✅ **High read performance** with strategic indexes
- ✅ **Scalability** with partitioning options
- ✅ **Data integrity** with foreign keys and constraints
- ✅ **Audit trail** with timestamps on all tables

**Next Steps:**
1. Create SQLAlchemy models based on this schema
2. Write Alembic migrations
3. Generate seed data for testing