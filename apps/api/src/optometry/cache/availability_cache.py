from datetime import date, datetime

from redis import Redis
from redis.exceptions import RedisError

from optometry.schemas.availability import AvailabilityRead

CACHE_TTL_SECONDS = 30


# loads the current cache version for a doctor and date
def get_availability_version(
    *,
    client: Redis,
    optometrist_id: int,
    appointment_date: date,
) -> int | None:
    key = f"availability:version:doctor:{optometrist_id}:date:{appointment_date}"

    try:
        value = client.get(key)
        if value is None:
            return 0
        if isinstance(value, (str, bytes)):
            return int(value)
    except (RedisError, ValueError):
        return None

    return None


# increments the version to invalidate previous availability results
def invalidate_availability(
    *,
    client: Redis,
    optometrist_id: int,
    appointment_date: date,
) -> bool:
    key = f"availability:version:doctor:{optometrist_id}:date:{appointment_date}"

    try:
        client.incr(key)
        return True
    except RedisError:
        return False


# builds a key using booking and administrative cache versions
def availability_cache_key(
    *,
    clinic_id: int,
    optometrist_id: int,
    service_id: int,
    appointment_date: date,
    version: int,
    clinic_version: int = 0,
    doctor_version: int = 0,
    service_version: int = 0,
) -> str:
    return (
        f"availability:v3:doctor:{optometrist_id}:"
        f"date:{appointment_date.isoformat()}:"
        f"version:{version}:"
        f"clinic:{clinic_id}:cv:{clinic_version}:"
        f"dv:{doctor_version}:"
        f"service:{service_id}:sv:{service_version}"
    )


# loads a cached response and removes expired time slots
def get_cached_availability(
    *,
    client: Redis,
    key: str,
    now: datetime,
) -> AvailabilityRead | None:
    try:
        cached = client.get(key)
    except RedisError:
        return None

    if cached is None:
        return None

    # validate the cached value before parsing json
    if not isinstance(cached, (str, bytes, bytearray)):
        return None

    try:
        availability = AvailabilityRead.model_validate_json(cached)
    except ValueError:
        return None

    availability.slots = [slot for slot in availability.slots if slot.start > now]

    return availability


# stores availability in redis with a short expiration time
def cache_availability(
    *,
    client: Redis,
    key: str,
    availability: AvailabilityRead,
) -> None:
    try:
        client.set(
            key,
            availability.model_dump_json(),
            ex=CACHE_TTL_SECONDS,
        )
    except RedisError:
        pass


# loads the version for an administrative cache scope
def get_scope_version(client: Redis, scope: str, entity_id: int) -> int | None:
    try:
        value = client.get(f"availability:version:{scope}:{entity_id}")
        if value is None:
            return 0
        if isinstance(value, (str, bytes)):
            return int(value)
    except (RedisError, ValueError):
        return None

    return None


# invalidates cached availability for an administrative scope
def invalidate_scope(client: Redis, scope: str, entity_id: int) -> bool:
    try:
        client.incr(f"availability:version:{scope}:{entity_id}")
        return True
    except RedisError:
        return False
