"""Tests for the LangChain appointment booking tool."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from optometry.agent.tools.booking import (
    create_booking_tool,
    fetch_book_appointment,
)


# checks successful appointment booking
def test_fetch_book_appointment() -> None:
    db = MagicMock()
    start = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    end = start + timedelta(minutes=20)

    appointment = SimpleNamespace(
        id=42,
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=start,
        end_at=end,
        appointment_price=Decimal("95.00"),
        status="booked",
    )

    with patch(
        "optometry.agent.tools.booking.create_appointment",
        return_value=appointment,
    ) as mock_create:
        result = fetch_book_appointment(
            db=db,
            patient_id=7,
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=start,
            now=datetime(2026, 11, 4, tzinfo=UTC),
        )

    assert result["appointment_id"] == 42
    assert result["status"] == "booked"
    assert result["appointment_price"] == "95.00"
    assert mock_create.call_args.kwargs["patient_id"] == 7


# checks booking conflicts
def test_fetch_book_appointment_conflict() -> None:
    with patch(
        "optometry.agent.tools.booking.create_appointment",
        side_effect=HTTPException(
            status_code=409,
            detail="Appointment slot is already booked",
        ),
    ):
        result = fetch_book_appointment(
            db=MagicMock(),
            patient_id=7,
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=datetime(2026, 11, 10, tzinfo=UTC),
            now=datetime(2026, 11, 4, tzinfo=UTC),
        )

    assert result == {
        "error": "Appointment slot is already booked",
        "status_code": 409,
    }


# checks that unconfirmed bookings are blocked
def test_booking_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation"):
        create_booking_tool(patient_id=7, confirmed=False)


# checks that invalid patient ids are blocked
def test_booking_requires_authenticated_patient() -> None:
    with pytest.raises(ValueError, match="authenticated patient"):
        create_booking_tool(patient_id=0, confirmed=True)


# checks the tool books for the trusted patient
def test_booking_tool_execution() -> None:
    expected = {"appointment_id": 42, "status": "booked"}
    start = "2026-11-10T15:00:00+00:00"

    with (
        patch("optometry.agent.tools.booking.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.booking.fetch_book_appointment",
            return_value=expected,
        ) as mock_fetch,
    ):
        booking_tool = create_booking_tool(
            patient_id=7,
            confirmed=True,
        )

        result = booking_tool.invoke(
            {
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": start,
            }
        )

    assert result == expected
    assert mock_fetch.call_args.kwargs["patient_id"] == 7
    assert mock_fetch.call_args.kwargs["start_at"] == datetime.fromisoformat(start)
    mock_session.assert_called_once_with()


# checks that the llm cannot supply a patient id
def test_booking_schema_excludes_patient_id() -> None:
    booking_tool = create_booking_tool(
        patient_id=7,
        confirmed=True,
    )

    assert "patient_id" not in booking_tool.args
    assert "confirmed" not in booking_tool.args


# checks invalid clinic ids are rejected
def test_booking_rejects_invalid_clinic_id() -> None:
    booking_tool = create_booking_tool(
        patient_id=7,
        confirmed=True,
    )

    with pytest.raises(ValidationError):
        booking_tool.invoke(
            {
                "clinic_id": -1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": "2026-11-10T15:00:00+00:00",
            }
        )
