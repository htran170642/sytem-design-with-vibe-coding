"""
Unit tests for OrderEvent — pure Python, no external dependencies.

Covers:
- create()    factory method
- from_dict() deserialisation from Redis Stream fields
- to_dict()   serialisation back to flat string dict
- Immutability (frozen dataclass)
- Schema version defaults
- Missing required fields raise KeyError
"""

import uuid
from datetime import UTC, datetime

import pytest

from shared.stream_schema import OrderEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_dict(**overrides: str) -> dict[str, str]:
    base = {
        "order_id": str(uuid.uuid4()),
        "user_id": "user-1",
        "product_id": "prod-1",
        "timestamp": "2026-03-05T10:00:00+00:00",
    }
    base.update(overrides)
    return base


# ===========================================================================
# OrderEvent.create()
# ===========================================================================


def test_create_returns_order_event() -> None:
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    assert isinstance(event, OrderEvent)


def test_create_sets_all_fields() -> None:
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    assert event.order_id == "o1"
    assert event.user_id == "u1"
    assert event.product_id == "p1"


def test_create_timestamp_is_utc_iso() -> None:
    """timestamp must be a parseable ISO-8601 string in UTC."""
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    dt = datetime.fromisoformat(event.timestamp)
    assert dt.tzinfo is not None
    # UTC offset must be 0
    assert dt.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_create_version_is_schema_version() -> None:
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    assert event.version == "1"


def test_create_is_immutable() -> None:
    """OrderEvent is a frozen dataclass — mutation must raise."""
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    with pytest.raises((AttributeError, TypeError)):
        event.order_id = "changed"  # type: ignore[misc]


# ===========================================================================
# OrderEvent.from_dict()
# ===========================================================================


def test_from_dict_roundtrip() -> None:
    """from_dict(to_dict(event)) must reproduce the original event."""
    original = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    restored = OrderEvent.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_sets_all_fields() -> None:
    data = _minimal_dict()
    event = OrderEvent.from_dict(data)
    assert event.order_id == data["order_id"]
    assert event.user_id == data["user_id"]
    assert event.product_id == data["product_id"]
    assert event.timestamp == data["timestamp"]


def test_from_dict_uses_version_field_if_present() -> None:
    data = _minimal_dict(version="2")
    event = OrderEvent.from_dict(data)
    assert event.version == "2"


def test_from_dict_defaults_version_if_missing() -> None:
    data = _minimal_dict()
    data.pop("version", None)
    event = OrderEvent.from_dict(data)
    assert event.version == "1"


def test_from_dict_missing_order_id_raises() -> None:
    data = _minimal_dict()
    del data["order_id"]
    with pytest.raises(KeyError):
        OrderEvent.from_dict(data)


def test_from_dict_missing_user_id_raises() -> None:
    data = _minimal_dict()
    del data["user_id"]
    with pytest.raises(KeyError):
        OrderEvent.from_dict(data)


def test_from_dict_missing_product_id_raises() -> None:
    data = _minimal_dict()
    del data["product_id"]
    with pytest.raises(KeyError):
        OrderEvent.from_dict(data)


# ===========================================================================
# OrderEvent.to_dict()
# ===========================================================================


def test_to_dict_returns_all_required_keys() -> None:
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    d = event.to_dict()
    assert "order_id" in d
    assert "user_id" in d
    assert "product_id" in d
    assert "timestamp" in d
    assert "version" in d


def test_to_dict_all_values_are_strings() -> None:
    """Redis Streams only accept string values."""
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    d = event.to_dict()
    for k, v in d.items():
        assert isinstance(v, str), f"{k!r} value is not a str: {v!r}"


def test_to_dict_values_match_event_fields() -> None:
    event = OrderEvent.create(order_id="o1", user_id="u1", product_id="p1")
    d = event.to_dict()
    assert d["order_id"] == event.order_id
    assert d["user_id"] == event.user_id
    assert d["product_id"] == event.product_id
    assert d["timestamp"] == event.timestamp
    assert d["version"] == event.version


# ===========================================================================
# Equality and identity
# ===========================================================================


def test_two_events_with_same_fields_are_equal() -> None:
    ts = datetime.now(tz=UTC).isoformat()
    e1 = OrderEvent(order_id="o1", user_id="u1", product_id="p1", timestamp=ts)
    e2 = OrderEvent(order_id="o1", user_id="u1", product_id="p1", timestamp=ts)
    assert e1 == e2


def test_two_events_with_different_order_ids_are_not_equal() -> None:
    ts = datetime.now(tz=UTC).isoformat()
    e1 = OrderEvent(order_id="o1", user_id="u1", product_id="p1", timestamp=ts)
    e2 = OrderEvent(order_id="o2", user_id="u1", product_id="p1", timestamp=ts)
    assert e1 != e2
