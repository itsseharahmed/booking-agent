"""Tests for the LangChain appointment cancellation tool."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from test_confirmation_tools import FakeRedis

from optometry.agent.tools.cancellation import (
    create_cancellation_tool,
    fetch_cancel_appointment,
)
from optometry.agent.tools.confirmation import (
    CancellationDetails,
    confirm_request,
    prepare_confirmation,
)


# checks successful cancellation and cache invalidation
def test_fetch_cancel_appointment() -> None:
    db = MagicMock()
    redis_client = MagicMock()
    now = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
    start = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)

    appointment = SimpleNamespace(
        id=42,
        optometrist_id=2,
        start_at=start,
        status="cancelled",
        cancelled_at=now,
    )

    with (
        patch(
            "optometry.agent.tools.cancellation.cancel_appointment",
            return_value=appointment,
        ) as mock_cancel,
        patch(
            "optometry.agent.tools.cancellation.invalidate_availability"
        ) as mock_invalidate,
    ):
        result = fetch_cancel_appointment(
            db=db,
            patient_id=7,
            appointment_id=42,
            now=now,
            redis_client=redis_client,
        )

    mock_cancel.assert_called_once_with(
        db,
        42,
        patient_id=7,
        now=now,
    )

    mock_invalidate.assert_called_once_with(
        client=redis_client,
        optometrist_id=2,
        appointment_date=start.astimezone(ZoneInfo("America/Toronto")).date(),
    )

    assert result == {
        "appointment_id": 42,
        "status": "cancelled",
        "cancelled_at": now.isoformat(),
    }


# checks appointment ownership errors
def test_cancel_appointment_not_found() -> None:
    with (
        patch(
            "optometry.agent.tools.cancellation.cancel_appointment",
            side_effect=HTTPException(
                status_code=404,
                detail="Appointment not found",
            ),
        ),
        patch(
            "optometry.agent.tools.cancellation.invalidate_availability"
        ) as mock_invalidate,
    ):
        result = fetch_cancel_appointment(
            db=MagicMock(),
            patient_id=7,
            appointment_id=999,
            now=datetime.now(UTC),
            redis_client=MagicMock(),
        )

    assert result == {
        "error": "Appointment not found",
        "status_code": 404,
    }
    mock_invalidate.assert_not_called()


# checks cancellation conflicts
def test_cancel_appointment_conflict() -> None:
    with (
        patch(
            "optometry.agent.tools.cancellation.cancel_appointment",
            side_effect=HTTPException(
                status_code=409,
                detail="Appointment is already cancelled",
            ),
        ),
        patch(
            "optometry.agent.tools.cancellation.invalidate_availability"
        ) as mock_invalidate,
    ):
        result = fetch_cancel_appointment(
            db=MagicMock(),
            patient_id=7,
            appointment_id=42,
            now=datetime.now(UTC),
            redis_client=MagicMock(),
        )

    assert result["status_code"] == 409
    mock_invalidate.assert_not_called()


# checks confirmation token is required
def test_cancellation_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation token"):
        create_cancellation_tool(
            patient_id=7,
            confirmation_token="",
        )


# checks authenticated patient is required
def test_cancellation_requires_authenticated_patient() -> None:
    with pytest.raises(ValueError, match="authenticated patient"):
        create_cancellation_tool(
            patient_id=0,
            confirmation_token="test-token",
        )


# checks cancellation uses the approved appointment id
def test_cancellation_tool_execution() -> None:
    redis_client = FakeRedis()

    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    expected = {
        "appointment_id": 42,
        "status": "cancelled",
        "cancelled_at": "2026-11-04T15:00:00+00:00",
    }

    with (
        patch(
            "optometry.agent.tools.cancellation.create_redis_client",
            return_value=redis_client,
        ),
        patch("optometry.agent.tools.cancellation.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.cancellation.fetch_cancel_appointment",
            return_value=expected,
        ) as mock_fetch,
    ):
        cancellation_tool = create_cancellation_tool(
            patient_id=7,
            confirmation_token=token,
        )

        result = cancellation_tool.invoke({})

        with pytest.raises(PermissionError):
            cancellation_tool.invoke({})

    assert result == expected
    assert mock_fetch.call_args.kwargs["patient_id"] == 7
    assert mock_fetch.call_args.kwargs["appointment_id"] == 42
    assert mock_fetch.call_args.kwargs["now"].tzinfo is UTC
    mock_fetch.assert_called_once()
    mock_session.assert_called_once_with()


# checks the llm cannot select an appointment to cancel
def test_cancellation_schema_excludes_patient_supplied_values() -> None:
    cancellation_tool = create_cancellation_tool(
        patient_id=7,
        confirmation_token="test-token",
    )

    assert cancellation_tool.args == {}
