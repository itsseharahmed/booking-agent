"""Tests for pure appointment slot generation."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from optometry.availability.engine import generate_slots

TORONTO = ZoneInfo("America/Toronto")


def test_generates_twenty_minute_slots() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 0),
        shift_end=time(10, 0),
    )

    assert len(slots) == 3
    assert [slot.start.time() for slot in slots] == [
        time(9, 0),
        time(9, 20),
        time(9, 40),
    ]
    assert slots[-1].end.time() == time(10, 0)


def test_excludes_partial_final_slot() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 0),
        shift_end=time(9, 50),
    )

    assert len(slots) == 2


def test_slots_anchor_to_shift_start() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 10),
        shift_end=time(10, 10),
    )

    assert [slot.start.time() for slot in slots] == [
        time(9, 10),
        time(9, 30),
        time(9, 50),
    ]


def test_short_shift_returns_no_slots() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 0),
        shift_end=time(9, 15),
    )

    assert slots == []


def test_invalid_shift_rejected() -> None:
    with pytest.raises(ValueError):
        generate_slots(
            appointment_date=date(2026, 11, 2),
            shift_start=time(17, 0),
            shift_end=time(9, 0),
        )


def test_excludes_past_and_current_slots() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 0),
        shift_end=time(10, 0),
        now=datetime(2026, 11, 2, 9, 20, tzinfo=TORONTO),
    )

    assert len(slots) == 1
    assert slots[0].start.time() == time(9, 40)


def test_rejects_naive_now() -> None:
    with pytest.raises(ValueError):
        generate_slots(
            appointment_date=date(2026, 11, 2),
            shift_start=time(9, 0),
            shift_end=time(10, 0),
            now=datetime(2026, 11, 2, 9, 0),
        )


def test_returns_timezone_aware_slots() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 7, 6),
        shift_start=time(9, 0),
        shift_end=time(9, 40),
    )

    assert all(slot.start.tzinfo is not None for slot in slots)
    assert slots[0].start.utcoffset().total_seconds() == -14400


def test_spring_dst_gap_excluded() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 3, 8),
        shift_start=time(1, 40),
        shift_end=time(3, 20),
    )

    assert all(slot.start.hour != 2 for slot in slots)
    assert all(slot.end.hour != 2 for slot in slots)


def test_fall_dst_ambiguity_excluded() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 1),
        shift_start=time(0, 40),
        shift_end=time(2, 20),
    )

    assert all(slot.start.hour != 1 for slot in slots)
    assert all(slot.end.hour != 1 for slot in slots)


def test_utc_now_comparison() -> None:
    slots = generate_slots(
        appointment_date=date(2026, 11, 2),
        shift_start=time(9, 0),
        shift_end=time(10, 0),
        now=datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
    )

    assert [slot.start.time() for slot in slots] == [
        time(9, 20),
        time(9, 40),
    ]
