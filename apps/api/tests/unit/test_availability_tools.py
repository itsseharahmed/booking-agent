"""Tests for the LangChain availability tool."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from optometry.agent.tools.availability import (
    check_appointment_availability,
    fetch_appointment_availability,
)


# checks available slots and pricing
def test_fetch_appointment_availability() -> None:
    db = MagicMock()
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    start = now + timedelta(days=1)
    end = start + timedelta(minutes=20)

    with patch(
        "optometry.agent.tools.availability.get_availability",
        return_value=(
            Decimal("95.00"),
            [SimpleNamespace(start=start, end=end)],
        ),
    ) as mock_service:
        result = fetch_appointment_availability(
            db=db,
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            appointment_date=date(2026, 11, 5),
            now=now,
        )

    mock_service.assert_called_once_with(
        db=db,
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        appointment_date=date(2026, 11, 5),
        now=now,
    )

    assert result["appointment_price"] == "95.00"
    assert result["slots"] == [
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    ]


# checks that unavailable dates return no slots
def test_fetch_appointment_availability_no_slots() -> None:
    with patch(
        "optometry.agent.tools.availability.get_availability",
        return_value=(Decimal("95.00"), []),
    ):
        result = fetch_appointment_availability(
            db=MagicMock(),
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            appointment_date=date(2026, 11, 5),
            now=datetime.now(UTC),
        )

    assert result["slots"] == []


# checks that missing clinics return a structured error
def test_fetch_appointment_availability_missing_clinic() -> None:
    with patch(
        "optometry.agent.tools.availability.get_availability",
        side_effect=HTTPException(
            status_code=404,
            detail="Clinic not found",
        ),
    ):
        result = fetch_appointment_availability(
            db=MagicMock(),
            clinic_id=999,
            optometrist_id=2,
            service_id=3,
            appointment_date=date(2026, 11, 5),
            now=datetime.now(UTC),
        )

    assert result == {
        "error": "Clinic not found",
        "status_code": 404,
    }


# checks that invalid ids are rejected
def test_check_availability_rejects_invalid_id() -> None:
    with pytest.raises(ValidationError):
        check_appointment_availability.invoke(
            {
                "clinic_id": -1,
                "optometrist_id": 2,
                "service_id": 3,
                "appointment_date": "2026-11-05",
            }
        )


# checks the langchain tool uses a database session
def test_check_appointment_availability() -> None:
    expected = {
        "clinic_id": 1,
        "optometrist_id": 2,
        "service_id": 3,
        "appointment_date": "2026-11-05",
        "appointment_price": "95.00",
        "slots": [],
    }

    with (
        patch("optometry.agent.tools.availability.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.availability.fetch_appointment_availability",
            return_value=expected,
        ) as mock_fetch,
    ):
        result = check_appointment_availability.invoke(
            {
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "appointment_date": "2026-11-05",
            }
        )

    assert result == expected
    mock_session.assert_called_once_with()

    arguments = mock_fetch.call_args.kwargs
    assert arguments["db"] is mock_session.return_value.__enter__.return_value
    assert arguments["clinic_id"] == 1
    assert arguments["optometrist_id"] == 2
    assert arguments["service_id"] == 3
    assert arguments["appointment_date"] == date(2026, 11, 5)
    assert arguments["now"].tzinfo is UTC
