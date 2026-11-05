"""Tests for booking and cancellation planning tools."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from optometry.agent.tools.planning import (
    propose_booking,
    propose_cancellation,
)


# checks booking proposals cannot execute appointments
def test_propose_booking() -> None:
    result = propose_booking.invoke(
        {
            "clinic_id": 1,
            "optometrist_id": 2,
            "service_id": 3,
            "start_at": datetime(2026, 11, 10, 15, tzinfo=UTC),
        }
    )

    assert result["action"] == "book"
    assert result["clinic_id"] == 1
    assert result["optometrist_id"] == 2
    assert result["service_id"] == 3
    assert result["requires_confirmation"] is True
    assert "appointment_id" not in result


# checks cancellation proposals cannot cancel appointments
def test_propose_cancellation() -> None:
    result = propose_cancellation.invoke({"appointment_id": 42})

    assert result == {
        "action": "cancel",
        "appointment_id": 42,
        "requires_confirmation": True,
    }


# checks invalid appointment ids are rejected
def test_propose_cancellation_rejects_invalid_id() -> None:
    with pytest.raises(ValidationError):
        propose_cancellation.invoke({"appointment_id": 0})


# checks booking time requires a timezone offset
def test_propose_booking_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone offset"):
        propose_booking.invoke(
            {
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": datetime(2026, 11, 10, 15),
            }
        )
