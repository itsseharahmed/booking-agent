"""Pure appointment availability calculations."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES

CLINIC_TIMEZONE = ZoneInfo("America/Toronto")


@dataclass(frozen=True)
class AvailabilitySlot:
    start: datetime
    end: datetime


def _valid_local_datetime(
    local_date: date,
    local_time: time,
) -> datetime | None:
    """Resolve an unambiguous, existing Toronto local time."""
    naive = datetime.combine(local_date, local_time)

    first = naive.replace(tzinfo=CLINIC_TIMEZONE, fold=0)
    second = naive.replace(tzinfo=CLINIC_TIMEZONE, fold=1)

    # Reject ambiguous times during the fall DST transition.
    if first.utcoffset() != second.utcoffset():
        return None

    # Reject nonexistent times during the spring DST transition.
    round_trip = first.astimezone(UTC).astimezone(CLINIC_TIMEZONE)

    if round_trip.replace(tzinfo=None) != naive:
        return None

    return first


def generate_slots(
    *,
    appointment_date: date,
    shift_start: time,
    shift_end: time,
    now: datetime | None = None,
) -> list[AvailabilitySlot]:
    """Generate 20-minute appointments within one working shift.

    Slots are anchored to the beginning of the shift.
    Partial appointments are excluded.
    Past slots are excluded when `now` is provided.
    Ambiguous and nonexistent local times are excluded.
    """
    if shift_start >= shift_end:
        raise ValueError("Shift start must precede shift end")

    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("now must be timezone-aware")

    duration = timedelta(minutes=APPOINTMENT_DURATION_MINUTES)

    cursor = datetime.combine(appointment_date, shift_start)
    shift_finish = datetime.combine(appointment_date, shift_end)

    slots: list[AvailabilitySlot] = []

    while cursor + duration <= shift_finish:
        start = _valid_local_datetime(
            appointment_date,
            cursor.time(),
        )
        end = _valid_local_datetime(
            appointment_date,
            (cursor + duration).time(),
        )

        if start is not None and end is not None:
            elapsed = end.astimezone(UTC) - start.astimezone(UTC)

            if elapsed == duration and (now is None or start > now):
                slots.append(AvailabilitySlot(start=start, end=end))

        cursor += duration

    return slots


def exclude_occupied_slots(
    slots: list[AvailabilitySlot],
    occupied: list[AvailabilitySlot],
) -> list[AvailabilitySlot]:
    """Exclude slots overlapping any occupied interval.

    Intervals are half-open: [start, end).
    Adjacent appointments therefore do not overlap.
    """
    for interval in occupied:
        if (
            interval.start.tzinfo is None
            or interval.end.tzinfo is None
            or interval.start.utcoffset() is None
            or interval.end.utcoffset() is None
        ):
            raise ValueError("Occupied intervals must be timezone-aware")

        if interval.start >= interval.end:
            raise ValueError("Occupied interval must have positive duration")

    return [
        slot
        for slot in slots
        if not any(
            slot.start < interval.end and interval.start < slot.end
            for interval in occupied
        )
    ]
