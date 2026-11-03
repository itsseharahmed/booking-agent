from redis import Redis

from optometry.cache.availability_cache import invalidate_scope


# invalidates availability after an administrative database change
def invalidate_admin_availability(
    client: Redis,
    *,
    clinic_id: int | None = None,
    optometrist_id: int | None = None,
    service_id: int | None = None,
) -> None:
    if clinic_id is not None:
        invalidate_scope(client, "clinic", clinic_id)

    if optometrist_id is not None:
        invalidate_scope(client, "doctor", optometrist_id)

    if service_id is not None:
        invalidate_scope(client, "service", service_id)
