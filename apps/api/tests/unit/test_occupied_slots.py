"""Tests for occupied appointment interval filtering."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from optometry.availability.engine import (
    AvailabilitySlot,
    exclude_occupied_slots,
)

TORONTO = ZoneInfo("America/Toronto")


def slot(start_hour: int, start_minute: int, end_hour: int, end_minute: int):
    return AvailabilitySlot(
        start=datetime(2026, 11, 2, start_hour, start_minute, tzinfo=TORONTO),
        end=datetime(2026, 11, 2, end_hour, end_minute, tzinfo=TORONTO),
    )


def test_exact_occupied_slot_is_excluded():
    available = [
        slot(9, 0, 9, 20),
        slot(9, 20, 9, 40),
        slot(9, 40, 10, 0),
    ]

    result = exclude_occupied_slots(
        available,
        [slot(9, 20, 9, 40)],
    )

    assert result == [available[0], available[2]]


def test_partial_overlap_is_excluded():
    available = [
        slot(9, 0, 9, 20),
        slot(9, 20, 9, 40),
    ]

    result = exclude_occupied_slots(
        available,
        [slot(9, 10, 9, 30)],
    )

    assert result == []


def test_adjacent_appointments_are_allowed():
    available = [
        slot(9, 0, 9, 20),
        slot(9, 20, 9, 40),
    ]

    result = exclude_occupied_slots(
        available,
        [slot(9, 20, 9, 40)],
    )

    assert result == [available[0]]


def test_long_occupied_interval_blocks_multiple_slots():
    available = [
        slot(9, 0, 9, 20),
        slot(9, 20, 9, 40),
        slot(9, 40, 10, 0),
    ]

    result = exclude_occupied_slots(
        available,
        [slot(9, 10, 9, 50)],
    )

    assert result == []


def test_empty_occupied_list_preserves_slots():
    available = [slot(9, 0, 9, 20)]

    assert exclude_occupied_slots(available, []) == available


def test_invalid_occupied_interval_rejected():
    with pytest.raises(ValueError):
        exclude_occupied_slots(
            [],
            [slot(10, 0, 9, 0)],
        )


def test_naive_occupied_interval_rejected():
    occupied = AvailabilitySlot(
        start=datetime(2026, 11, 2, 9, 0),
        end=datetime(2026, 11, 2, 9, 20),
    )

    with pytest.raises(ValueError):
        exclude_occupied_slots([], [occupied])
