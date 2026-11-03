from datetime import date
from unittest.mock import Mock

from redis.exceptions import ConnectionError

from optometry.cache.availability_cache import (
    availability_cache_key,
    get_availability_version,
    get_scope_version,
    invalidate_availability,
    invalidate_scope,
)


# checks that booking invalidation changes the cache key
def test_booking_invalidation_changes_cache_key() -> None:
    client = Mock()
    client.get.side_effect = [None, "1"]

    appointment_date = date(2026, 11, 9)

    before = get_availability_version(
        client=client,
        optometrist_id=2,
        appointment_date=appointment_date,
    )

    assert invalidate_availability(
        client=client,
        optometrist_id=2,
        appointment_date=appointment_date,
    )

    after = get_availability_version(
        client=client,
        optometrist_id=2,
        appointment_date=appointment_date,
    )

    assert before is not None
    assert after is not None

    old_key = availability_cache_key(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        appointment_date=appointment_date,
        version=before,
    )

    new_key = availability_cache_key(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        appointment_date=appointment_date,
        version=after,
    )

    assert old_key != new_key


# checks that administrative invalidation changes the cache version
def test_admin_invalidation_changes_version() -> None:
    client = Mock()
    client.get.side_effect = [None, "1"]

    before = get_scope_version(client, "clinic", 1)

    assert invalidate_scope(client, "clinic", 1)

    after = get_scope_version(client, "clinic", 1)

    assert before == 0
    assert after == 1


# checks that failed redis reads disable caching
def test_redis_read_failure() -> None:
    client = Mock()
    client.get.side_effect = ConnectionError("Redis unavailable")

    assert (
        get_availability_version(
            client=client,
            optometrist_id=2,
            appointment_date=date(2026, 11, 9),
        )
        is None
    )

    assert get_scope_version(client, "clinic", 1) is None


# checks that failed redis invalidation does not raise
def test_redis_invalidation_failure() -> None:
    client = Mock()
    client.incr.side_effect = ConnectionError("Redis unavailable")

    assert (
        invalidate_availability(
            client=client,
            optometrist_id=2,
            appointment_date=date(2026, 11, 9),
        )
        is False
    )

    assert invalidate_scope(client, "clinic", 1) is False
