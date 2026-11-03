# Pure appointment availability calculations.

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from optometry.core.appointments import APPOINTMENT_DURATION_MINUTES

CLINIC_TIMEZONE = ZoneInfo("America/Toronto")


@dataclass(frozen=True)
# stores a single appointment time range as a start and end datetime.
class AvailabilitySlot:
    start: datetime
    end: datetime


# resolves a local Toronto time into a real timezone-aware datetime or rejects invalid cases.
def _valid_local_datetime(
    local_date: date,
    local_time: time,
) -> datetime | None:
    """Resolve an unambiguous, existing Toronto local time."""
    # combine the date and time into a naive local datetime before checking timezone rules.
    naive = datetime.combine(local_date, local_time)

    # test both fold values so ambiguous DST times are detected correctly.
    first = naive.replace(tzinfo=CLINIC_TIMEZONE, fold=0)
    second = naive.replace(tzinfo=CLINIC_TIMEZONE, fold=1)

    # reject ambiguous times during the fall DST transition.
    if first.utcoffset() != second.utcoffset():
        return None

    # reject nonexistent times during the spring DST transition.
    round_trip = first.astimezone(UTC).astimezone(CLINIC_TIMEZONE)

    if round_trip.replace(tzinfo=None) != naive:
        return None

    return first


# builds every possible appointment start time inside a shift.
def generate_slots(
    *,
    appointment_date: date,
    shift_start: time,
    shift_end: time,
    now: datetime | None = None,
) -> list[AvailabilitySlot]:
    # a shift must start before it ends or the calendar logic would be invalid.
    if shift_start >= shift_end:
        raise ValueError("Shift start must precede shift end")

    # the current time must include a timezone if it is passed in.
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("now must be timezone-aware")

    # appointment duration is fixed by the project rule.
    duration = timedelta(minutes=APPOINTMENT_DURATION_MINUTES)

    # the cursor moves forward in equal appointment-length steps across the shift.
    cursor = datetime.combine(appointment_date, shift_start)
    shift_finish = datetime.combine(appointment_date, shift_end)

    slots: list[AvailabilitySlot] = []

    # keep generating slots while one full appointment still fits into the shift.
    while cursor + duration <= shift_finish:
        # check the actual start and end local times for DST correctness.
        start = _valid_local_datetime(
            appointment_date,
            cursor.time(),
        )
        end = _valid_local_datetime(
            appointment_date,
            (cursor + duration).time(),
        )

        # only keep slots when both times are valid and this slot is in the future.
        if start is not None and end is not None:
            elapsed = end.astimezone(UTC) - start.astimezone(UTC)

            if elapsed == duration and (now is None or start > now):
                slots.append(AvailabilitySlot(start=start, end=end))

        cursor += duration

    return slots


# removes every slot that overlaps with an already booked appointment period.
def exclude_occupied_slots(
    slots: list[AvailabilitySlot],
    occupied: list[AvailabilitySlot],
) -> list[AvailabilitySlot]:
    # validate each occupied range before comparing it to available slots.
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

    # keep only the free intervals that do not overlap with any occupied block.
    return [
        slot
        for slot in slots
        if not any(
            slot.start < interval.end and interval.start < slot.end
            for interval in occupied
        )
    ]
