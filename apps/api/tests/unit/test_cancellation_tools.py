"""Tests for the LangChain appointment cancellation tool."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from optometry.agent.tools.cancellation import (
    create_cancellation_tool,
    fetch_cancel_appointment,
)


# checks successful appointment cancellation
def test_fetch_cancel_appointment() -> None:
    db = MagicMock()
    now = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)

    appointment = SimpleNamespace(
        id=42,
        status="cancelled",
        cancelled_at=now,
    )

    with patch(
        "optometry.agent.tools.cancellation.cancel_appointment",
        return_value=appointment,
    ) as mock_cancel:
        result = fetch_cancel_appointment(
            db=db,
            patient_id=7,
            appointment_id=42,
            now=now,
        )

    mock_cancel.assert_called_once_with(
        db,
        42,
        patient_id=7,
        now=now,
    )

    assert result == {
        "appointment_id": 42,
        "status": "cancelled",
        "cancelled_at": now.isoformat(),
    }


# checks appointment ownership errors
def test_cancel_appointment_not_found() -> None:
    with patch(
        "optometry.agent.tools.cancellation.cancel_appointment",
        side_effect=HTTPException(
            status_code=404,
            detail="Appointment not found",
        ),
    ):
        result = fetch_cancel_appointment(
            db=MagicMock(),
            patient_id=7,
            appointment_id=999,
            now=datetime.now(UTC),
        )

    assert result == {
        "error": "Appointment not found",
        "status_code": 404,
    }


# checks cancellation conflicts
def test_cancel_appointment_conflict() -> None:
    with patch(
        "optometry.agent.tools.cancellation.cancel_appointment",
        side_effect=HTTPException(
            status_code=409,
            detail="Appointment is already cancelled",
        ),
    ):
        result = fetch_cancel_appointment(
            db=MagicMock(),
            patient_id=7,
            appointment_id=42,
            now=datetime.now(UTC),
        )

    assert result["status_code"] == 409


# checks that unconfirmed cancellations are blocked
def test_cancellation_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation"):
        create_cancellation_tool(patient_id=7, confirmed=False)


# checks that invalid patient ids are blocked
def test_cancellation_requires_authenticated_patient() -> None:
    with pytest.raises(ValueError, match="authenticated patient"):
        create_cancellation_tool(patient_id=0, confirmed=True)


# checks the tool uses the authenticated patient
def test_cancellation_tool_execution() -> None:
    expected = {
        "appointment_id": 42,
        "status": "cancelled",
        "cancelled_at": "2026-11-04T15:00:00+00:00",
    }

    with (
        patch("optometry.agent.tools.cancellation.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.cancellation.fetch_cancel_appointment",
            return_value=expected,
        ) as mock_fetch,
    ):
        cancellation_tool = create_cancellation_tool(
            patient_id=7,
            confirmed=True,
        )

        result = cancellation_tool.invoke({"appointment_id": 42})

    assert result == expected
    assert mock_fetch.call_args.kwargs["patient_id"] == 7
    assert mock_fetch.call_args.kwargs["appointment_id"] == 42
    assert mock_fetch.call_args.kwargs["now"].tzinfo is UTC
    mock_session.assert_called_once_with()


# checks that the llm cannot supply patient identity
def test_cancellation_schema_excludes_patient_id() -> None:
    cancellation_tool = create_cancellation_tool(
        patient_id=7,
        confirmed=True,
    )

    assert "patient_id" not in cancellation_tool.args
    assert "confirmed" not in cancellation_tool.args


# checks invalid appointment ids are rejected
def test_cancellation_rejects_invalid_id() -> None:
    cancellation_tool = create_cancellation_tool(
        patient_id=7,
        confirmed=True,
    )

    with pytest.raises(ValidationError):
        cancellation_tool.invoke({"appointment_id": -1})
