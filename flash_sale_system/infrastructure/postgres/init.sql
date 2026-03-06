-- Flash sale orders schema
-- Run once to initialise the database before starting the worker.
-- Phase 5 will add full Alembic migrations on top of this baseline.

-- ---------------------------------------------------------------------------
-- Enum: order status
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('fulfilled', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- Table: orders
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id          BIGSERIAL       PRIMARY KEY,
    order_id    UUID            NOT NULL,
    user_id     TEXT            NOT NULL,
    product_id  TEXT            NOT NULL,
    status      order_status    NOT NULL DEFAULT 'fulfilled',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- One purchase per user per product — enforced at DB level.
    -- worker/db.py uses ON CONFLICT (user_id, product_id) DO NOTHING
    -- to exploit this constraint for idempotent inserts.
    CONSTRAINT uq_user_product UNIQUE (user_id, product_id)
);

-- ---------------------------------------------------------------------------
-- Indexes (Phase 5 will add more; these cover the worker's access patterns)
-- ---------------------------------------------------------------------------

-- Fast lookup by order_id (used for status checks / deduplication audit)
CREATE INDEX IF NOT EXISTS idx_orders_order_id
    ON orders (order_id);

-- Fast lookup by product_id (used for stock reconciliation)
CREATE INDEX IF NOT EXISTS idx_orders_product_id
    ON orders (product_id);

-- Fast lookup by user_id (used for "has user bought?" checks)
CREATE INDEX IF NOT EXISTS idx_orders_user_id
    ON orders (user_id);

-- Time-range queries (used for reporting, partition candidate in Phase 5)
CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON orders (created_at DESC);
