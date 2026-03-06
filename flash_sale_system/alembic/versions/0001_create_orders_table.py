"""create_orders_table

Revision ID: 0001
Revises:
Create Date: 2026-03-04 22:59:35.199921

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE order_status AS ENUM ('fulfilled', 'failed')")

    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id          BIGSERIAL PRIMARY KEY,
            order_id    UUID        NOT NULL,
            user_id     TEXT        NOT NULL,
            product_id  TEXT        NOT NULL,
            status      order_status NOT NULL DEFAULT 'fulfilled',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_product UNIQUE (user_id, product_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id   ON orders (order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders (product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id    ON orders (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS orders")
    op.execute("DROP TYPE IF EXISTS order_status")
