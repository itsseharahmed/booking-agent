"""Read-only appointment availability API."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis import Redis
from sqlalchemy.orm import Session

from optometry.availability.service import get_availability
from optometry.cache.availability_cache import (
    availability_cache_key,
    cache_availability,
    get_availability_version,
    get_cached_availability,
    get_scope_version,
)
from optometry.cache.redis_client import create_redis_client
from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES
from optometry.db.session import get_db
from optometry.schemas.availability import (
    AvailabilityRead,
    AvailabilitySlotRead,
)

router = APIRouter(prefix="/availability", tags=["Availability"])

DbSession = Annotated[Session, Depends(get_db)]


# provides the redis client for availability requests
def get_redis_client() -> Redis:
    return create_redis_client()


RedisClient = Annotated[Redis, Depends(get_redis_client)]


@router.get("", response_model=AvailabilityRead)
def list_availability(
    db: DbSession,
    redis_client: RedisClient,
    clinic_id: Annotated[int, Query(gt=0)],
    optometrist_id: Annotated[int, Query(gt=0)],
    service_id: Annotated[int, Query(gt=0)],
    appointment_date: date,
) -> AvailabilityRead:
    # capture the current time for consistent slot filtering
    now = get_current_time()

    # load the booking cache version
    version = get_availability_version(
        client=redis_client,
        optometrist_id=optometrist_id,
        appointment_date=appointment_date,
    )

    # load administrative cache versions
    clinic_version = get_scope_version(
        redis_client,
        "clinic",
        clinic_id,
    )
    doctor_version = get_scope_version(
        redis_client,
        "doctor",
        optometrist_id,
    )
    service_version = get_scope_version(
        redis_client,
        "service",
        service_id,
    )

    versions = (
        version,
        clinic_version,
        doctor_version,
        service_version,
    )

    # only use redis when all cache versions are available
    if (
        version is not None
        and clinic_version is not None
        and doctor_version is not None
        and service_version is not None
    ):
        key = availability_cache_key(
            clinic_id=clinic_id,
            optometrist_id=optometrist_id,
            service_id=service_id,
            appointment_date=appointment_date,
            version=version,
            clinic_version=clinic_version,
            doctor_version=doctor_version,
            service_version=service_version,
        )

        # return cached availability when the key exists
        cached = get_cached_availability(
            client=redis_client,
            key=key,
            now=now,
        )

        if cached is not None:
            return cached

    # calculate availability using the existing database service
    price, slots = get_availability(
        db=db,
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        appointment_date=appointment_date,
        now=now,
    )

    # build the availability response
    availability = AvailabilityRead(
        clinic_id=clinic_id,
        optometrist_id=optometrist_id,
        service_id=service_id,
        appointment_date=appointment_date,
        timezone="America/Toronto",
        duration_minutes=APPOINTMENT_DURATION_MINUTES,
        appointment_price=price,
        slots=[AvailabilitySlotRead(start=slot.start, end=slot.end) for slot in slots],
    )

    # verify all cache versions before storing the response
    if (
        version is not None
        and clinic_version is not None
        and doctor_version is not None
        and service_version is not None
    ):
        current_versions = (
            get_availability_version(
                client=redis_client,
                optometrist_id=optometrist_id,
                appointment_date=appointment_date,
            ),
            get_scope_version(redis_client, "clinic", clinic_id),
            get_scope_version(redis_client, "doctor", optometrist_id),
            get_scope_version(redis_client, "service", service_id),
        )

        # avoid caching results after an invalidation
        if current_versions == versions:
            cache_availability(
                client=redis_client,
                key=key,
                availability=availability,
            )

    return availability


# provides a replaceable utc clock for availability queries
def get_current_time() -> datetime:
    return datetime.now(UTC)
