"""Tests for transactional booking price protection."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from optometry.booking.service import create_appointment
from optometry.schemas.appointment import AppointmentCreate


# checks changed prices prevent appointment creation
def test_booking_rejects_changed_price_before_commit() -> None:
    db = MagicMock()
    start = datetime(2026, 11, 10, 15, tzinfo=UTC)

    db.scalar.return_value = SimpleNamespace(
        id=1,
        appointment_price=Decimal("110.00"),
    )

    payload = AppointmentCreate(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=start,
    )

    with (
        patch(
            "optometry.booking.service.get_availability",
            return_value=(
                Decimal("110.00"),
                [SimpleNamespace(start=start)],
            ),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        create_appointment(
            db,
            payload,
            patient_id=7,
            now=start - timedelta(days=1),
            expected_price=Decimal("95.00"),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == ("Appointment price changed. New confirmation required.")

    db.add.assert_not_called()
    db.commit.assert_not_called()


# checks the expected price is forwarded to the booking service
def test_agent_booking_passes_approved_price() -> None:
    from optometry.agent.tools.booking import fetch_book_appointment

    db = MagicMock()
    start = datetime(2026, 11, 10, 15, tzinfo=UTC)

    appointment = SimpleNamespace(
        id=42,
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=start,
        end_at=start + timedelta(minutes=20),
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
            now=start - timedelta(days=1),
            expected_price=Decimal("95.00"),
        )

    assert result["appointment_id"] == 42

    assert mock_create.call_args.kwargs["expected_price"] == Decimal("95.00")
