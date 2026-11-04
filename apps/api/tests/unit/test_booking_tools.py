"""Tests for the LangChain appointment booking tool."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from test_confirmation_tools import FakeRedis

from optometry.agent.tools.booking import (
    create_booking_tool,
    fetch_book_appointment,
)
from optometry.agent.tools.confirmation import (
    BookingDetails,
    confirm_request,
    prepare_confirmation,
)


# checks successful booking and cache invalidation
def test_fetch_book_appointment() -> None:
    db = MagicMock()
    redis_client = MagicMock()
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

    with (
        patch(
            "optometry.agent.tools.booking.create_appointment",
            return_value=appointment,
        ) as mock_create,
        patch(
            "optometry.agent.tools.booking.invalidate_availability"
        ) as mock_invalidate,
    ):
        result = fetch_book_appointment(
            db=db,
            patient_id=7,
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=start,
            now=datetime(2026, 11, 4, tzinfo=UTC),
            redis_client=redis_client,
        )

    assert result["appointment_id"] == 42
    assert result["status"] == "booked"
    assert result["appointment_price"] == "95.00"
    assert mock_create.call_args.kwargs["patient_id"] == 7

    mock_invalidate.assert_called_once_with(
        client=redis_client,
        optometrist_id=2,
        appointment_date=start.astimezone(ZoneInfo("America/Toronto")).date(),
    )


# checks booking conflicts do not invalidate cache
def test_fetch_book_appointment_conflict() -> None:
    with (
        patch(
            "optometry.agent.tools.booking.create_appointment",
            side_effect=HTTPException(
                status_code=409,
                detail="Appointment slot is already booked",
            ),
        ),
        patch(
            "optometry.agent.tools.booking.invalidate_availability"
        ) as mock_invalidate,
    ):
        result = fetch_book_appointment(
            db=MagicMock(),
            patient_id=7,
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=datetime(2026, 11, 10, tzinfo=UTC),
            now=datetime(2026, 11, 4, tzinfo=UTC),
            redis_client=MagicMock(),
        )

    assert result == {
        "error": "Appointment slot is already booked",
        "status_code": 409,
    }
    mock_invalidate.assert_not_called()


# checks confirmation token is required
def test_booking_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation token"):
        create_booking_tool(
            patient_id=7,
            confirmation_token="",
        )


# checks authenticated patient is required
def test_booking_requires_authenticated_patient() -> None:
    with pytest.raises(ValueError, match="authenticated patient"):
        create_booking_tool(
            patient_id=0,
            confirmation_token="test-token",
        )


# checks the tool books only approved details
def test_booking_tool_execution() -> None:
    redis_client = FakeRedis()
    start = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)

    details = BookingDetails(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=start,
    )

    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="book",
        details=details,
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    expected = {
        "appointment_id": 42,
        "status": "booked",
    }

    with (
        patch(
            "optometry.agent.tools.booking.create_redis_client",
            return_value=redis_client,
        ),
        patch("optometry.agent.tools.booking.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.booking.fetch_book_appointment",
            return_value=expected,
        ) as mock_fetch,
    ):
        booking_tool = create_booking_tool(
            patient_id=7,
            confirmation_token=token,
        )

        result = booking_tool.invoke({})

        with pytest.raises(PermissionError):
            booking_tool.invoke({})

    assert result == expected
    assert mock_fetch.call_args.kwargs["patient_id"] == 7
    assert mock_fetch.call_args.kwargs["clinic_id"] == 1
    assert mock_fetch.call_args.kwargs["optometrist_id"] == 2
    assert mock_fetch.call_args.kwargs["service_id"] == 3
    assert mock_fetch.call_args.kwargs["start_at"] == start
    mock_fetch.assert_called_once()
    mock_session.assert_called_once_with()


# checks the llm cannot change approved details
def test_booking_schema_excludes_patient_supplied_values() -> None:
    booking_tool = create_booking_tool(
        patient_id=7,
        confirmation_token="test-token",
    )

    assert booking_tool.args == {}
