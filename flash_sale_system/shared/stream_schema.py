"""
Redis Stream message schema for the orders stream.

Single source of truth used by:
  - API (producer)  — serialise via to_dict()
  - Worker (consumer) — deserialise via OrderEvent.from_dict()

Stream entry fields (all strings — Redis Streams only store strings):
  order_id    UUID v4
  user_id     caller-supplied user identifier
  product_id  product being purchased
  timestamp   ISO-8601 UTC, e.g. "2026-03-04T10:00:00.123456+00:00"
  version     schema version ("1") — allows backward-compat changes later
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    user_id: str
    product_id: str
    timestamp: str  # ISO-8601 UTC string
    version: str = _SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, *, order_id: str, user_id: str, product_id: str) -> OrderEvent:
        """Build a new event with the current UTC timestamp."""
        return cls(
            order_id=order_id,
            user_id=user_id,
            product_id=product_id,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> OrderEvent:
        """Deserialise from a Redis Stream entry (all values are strings)."""
        return cls(
            order_id=data["order_id"],
            user_id=data["user_id"],
            product_id=data["product_id"],
            timestamp=data["timestamp"],
            version=data.get("version", _SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, str]:
        """Serialise to a flat string dict suitable for XADD."""
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "timestamp": self.timestamp,
            "version": self.version,
        }
