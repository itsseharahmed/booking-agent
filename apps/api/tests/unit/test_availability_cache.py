from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from redis.exceptions import ConnectionError

from optometry.cache.admin_invalidation import invalidate_admin_availability
from optometry.cache.availability_cache import (
    availability_cache_key,
    cache_availability,
    get_cached_availability,
    get_scope_version,
    invalidate_scope,
)
from optometry.schemas.availability import (
    AvailabilityRead,
    AvailabilitySlotRead,
)


# creates an availability response for testing
def make_availability() -> AvailabilityRead:
    start = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)

    return AvailabilityRead(
        clinic_id=1,
        optometrist_id=2,
        service_id=1,
        appointment_date=date(2026, 11, 9),
        timezone="America/Toronto",
        duration_minutes=30,
        appointment_price=Decimal("100.00"),
        slots=[
            AvailabilitySlotRead(
                start=start,
                end=start + timedelta(minutes=30),
            )
        ],
    )


# checks that cache keys include the version and request parameters
def test_availability_cache_key() -> None:
    key = availability_cache_key(
        clinic_id=1,
        optometrist_id=2,
        service_id=1,
        appointment_date=date(2026, 11, 9),
        version=0,
    )

    assert key == (
        "availability:v3:doctor:2:"
        "date:2026-11-09:"
        "version:0:"
        "clinic:1:cv:0:"
        "dv:0:"
        "service:1:sv:0"
    )


# checks that availability is stored with a ttl
def test_cache_availability() -> None:
    client = Mock()
    availability = make_availability()

    cache_availability(
        client=client,
        key="test-key",
        availability=availability,
    )

    client.set.assert_called_once_with(
        "test-key",
        availability.model_dump_json(),
        ex=30,
    )


# checks that cached availability is restored correctly
def test_get_cached_availability() -> None:
    client = Mock()
    availability = make_availability()
    client.get.return_value = availability.model_dump_json()

    result = get_cached_availability(
        client=client,
        key="test-key",
        now=datetime(2026, 11, 9, 13, 0, tzinfo=UTC),
    )

    assert result == availability


# checks that past appointment slots are removed
def test_cached_availability_excludes_past_slots() -> None:
    client = Mock()
    availability = make_availability()
    client.get.return_value = availability.model_dump_json()

    result = get_cached_availability(
        client=client,
        key="test-key",
        now=datetime(2026, 11, 9, 15, 0, tzinfo=UTC),
    )

    assert result is not None
    assert result.slots == []


# checks that a redis failure falls back to a cache miss
def test_cache_failure_returns_none() -> None:
    client = Mock()
    client.get.side_effect = ConnectionError("Redis unavailable")

    result = get_cached_availability(
        client=client,
        key="test-key",
        now=datetime.now(UTC),
    )

    assert result is None


from optometry.cache.availability_cache import (
    get_availability_version,
    invalidate_availability,
)


# checks that a missing version starts at zero
def test_missing_availability_version() -> None:
    client = Mock()
    client.get.return_value = None

    version = get_availability_version(
        client=client,
        optometrist_id=2,
        appointment_date=date(2026, 11, 9),
    )

    assert version == 0


# checks that invalidation increments the version
def test_invalidate_availability() -> None:
    client = Mock()

    result = invalidate_availability(
        client=client,
        optometrist_id=2,
        appointment_date=date(2026, 11, 9),
    )

    assert result is True
    client.incr.assert_called_once_with("availability:version:doctor:2:date:2026-11-09")


# checks that redis failures disable version-based caching
def test_availability_version_redis_failure() -> None:
    client = Mock()
    client.get.side_effect = ConnectionError("Redis unavailable")

    version = get_availability_version(
        client=client,
        optometrist_id=2,
        appointment_date=date(2026, 11, 9),
    )

    assert version is None


# checks that missing administrative versions start at zero
def test_missing_scope_version() -> None:
    client = Mock()
    client.get.return_value = None

    assert get_scope_version(client, "clinic", 1) == 0
    client.get.assert_called_once_with("availability:version:clinic:1")


# checks that administrative invalidation increments the correct version
def test_invalidate_scope() -> None:
    client = Mock()

    assert invalidate_scope(client, "doctor", 2) is True
    client.incr.assert_called_once_with("availability:version:doctor:2")


# checks that all affected administrative scopes are invalidated
def test_invalidate_admin_availability() -> None:
    client = Mock()

    invalidate_admin_availability(
        client,
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
    )

    assert client.incr.call_count == 3
    client.incr.assert_any_call("availability:version:clinic:1")
    client.incr.assert_any_call("availability:version:doctor:2")
    client.incr.assert_any_call("availability:version:service:3")


# checks that redis failures do not interrupt invalidation
def test_invalidate_scope_redis_failure() -> None:
    client = Mock()
    client.incr.side_effect = ConnectionError("Redis unavailable")

    assert invalidate_scope(client, "clinic", 1) is False
