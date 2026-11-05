"""Integration tests for authenticated agent confirmations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis

from optometry.agent.tools.confirmation import (
    BookingDetails,
    CancellationDetails,
    confirm_request,
    consume_confirmation,
    prepare_confirmation,
)
from optometry.api.agent_confirmations import (
    get_confirmation_redis,
    router,
)
from optometry.auth.dependencies import get_current_patient
from optometry.db.session import get_db


@pytest.fixture
def client(test_redis: Redis) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_confirmation_redis] = lambda: test_redis
    app.dependency_overrides[get_current_patient] = lambda: SimpleNamespace(id=7)

    return TestClient(app)


# checks booking preparation stores the exact appointment
def test_prepare_booking(client: TestClient, test_redis: Redis) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    with patch(
        "optometry.api.agent_confirmations.get_availability",
        return_value=(
            Decimal("95.00"),
            [SimpleNamespace(start=start)],
        ),
    ):
        response = client.post(
            "/agent/confirmations/book",
            json={
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": start.isoformat(),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "book"
    assert data["details"]["appointment_price"] == "95.00"

    token = data["confirmation_token"]

    approved = client.post(f"/agent/confirmations/{token}/approve")

    assert approved.status_code == 200
    assert approved.json() == {"approved": True}

    details = consume_confirmation(
        client=test_redis,
        patient_id=7,
        token=token,
        action="book",
    )

    assert isinstance(details, BookingDetails)
    assert details.clinic_id == 1
    assert details.optometrist_id == 2
    assert details.service_id == 3
    assert details.start_at == start
    assert details.appointment_price == Decimal("95.00")


# checks unavailable slots cannot receive approvals
def test_prepare_booking_rejects_unavailable_slot(
    client: TestClient,
) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    with patch(
        "optometry.api.agent_confirmations.get_availability",
        return_value=(Decimal("95.00"), []),
    ):
        response = client.post(
            "/agent/confirmations/book",
            json={
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": start.isoformat(),
            },
        )

    assert response.status_code == 409


# checks cancellation preparation preserves appointment ownership
def test_prepare_cancellation(
    client: TestClient,
    test_redis: Redis,
) -> None:
    appointment = SimpleNamespace(
        id=42,
        status="booked",
        start_at=datetime.now(UTC) + timedelta(days=7),
    )

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        return_value=appointment,
    ) as mock_get:
        response = client.post(
            "/agent/confirmations/cancel",
            json={"appointment_id": 42},
        )

    assert response.status_code == 200
    assert mock_get.call_args.kwargs["patient_id"] == 7

    token = response.json()["confirmation_token"]

    assert client.post(f"/agent/confirmations/{token}/approve").status_code == 200

    details = consume_confirmation(
        client=test_redis,
        patient_id=7,
        token=token,
        action="cancel",
    )

    assert isinstance(details, CancellationDetails)
    assert details.appointment_id == 42


# checks cancellation requires ownership
def test_prepare_cancellation_rejects_unowned_appointment(
    client: TestClient,
) -> None:
    from fastapi import HTTPException

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        side_effect=HTTPException(
            status_code=404,
            detail="Appointment not found",
        ),
    ):
        response = client.post(
            "/agent/confirmations/cancel",
            json={"appointment_id": 999},
        )

    assert response.status_code == 404


# checks confirmation cannot be approved twice
def test_confirmation_cannot_be_approved_twice(
    client: TestClient,
) -> None:
    appointment = SimpleNamespace(
        id=42,
        status="booked",
        start_at=datetime.now(UTC) + timedelta(days=7),
    )

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        return_value=appointment,
    ):
        prepared = client.post(
            "/agent/confirmations/cancel",
            json={"appointment_id": 42},
        )

    token = prepared.json()["confirmation_token"]

    first = client.post(f"/agent/confirmations/{token}/approve")
    second = client.post(f"/agent/confirmations/{token}/approve")

    assert first.status_code == 200
    assert second.status_code == 409


# checks a different patient cannot approve the token
def test_confirmation_rejects_different_patient(
    client: TestClient,
) -> None:
    appointment = SimpleNamespace(
        id=42,
        status="booked",
        start_at=datetime.now(UTC) + timedelta(days=7),
    )

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        return_value=appointment,
    ):
        prepared = client.post(
            "/agent/confirmations/cancel",
            json={"appointment_id": 42},
        )

    token = prepared.json()["confirmation_token"]

    client.app.dependency_overrides[get_current_patient] = lambda: SimpleNamespace(id=8)

    response = client.post(f"/agent/confirmations/{token}/approve")

    assert response.status_code == 409


# checks endpoints reject requests without authentication
def test_confirmation_requires_authentication(
    test_redis: Redis,
) -> None:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_confirmation_redis] = lambda: test_redis

    with TestClient(app) as unauthenticated:
        response = unauthenticated.post(
            "/agent/confirmations/cancel",
            json={"appointment_id": 42},
        )

    assert response.status_code == 401


# checks approved booking executes with exact details
def test_execute_confirmed_booking(
    client: TestClient,
    test_redis: Redis,
) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    token = prepare_confirmation(
        client=test_redis,
        patient_id=7,
        action="book",
        details=BookingDetails(
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=start,
            appointment_price=Decimal("95.00"),
        ),
    )

    assert confirm_request(
        client=test_redis,
        patient_id=7,
        token=token,
    )

    expected = {
        "appointment_id": 42,
        "status": "booked",
    }

    with patch(
        "optometry.api.agent_confirmations.fetch_book_appointment",
        return_value=expected,
    ) as mock_book:
        response = client.post(f"/agent/confirmations/{token}/execute/book")

        replay = client.post(f"/agent/confirmations/{token}/execute/book")

    assert response.status_code == 200
    assert response.json() == expected
    assert replay.status_code == 409

    assert mock_book.call_count == 1
    assert mock_book.call_args.kwargs["patient_id"] == 7
    assert mock_book.call_args.kwargs["clinic_id"] == 1
    assert mock_book.call_args.kwargs["optometrist_id"] == 2
    assert mock_book.call_args.kwargs["service_id"] == 3
    assert mock_book.call_args.kwargs["start_at"] == start
    assert mock_book.call_args.kwargs["expected_price"] == Decimal("95.00")


# checks approved cancellation executes only once
def test_execute_confirmed_cancellation(
    client: TestClient,
    test_redis: Redis,
) -> None:
    token = prepare_confirmation(
        client=test_redis,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=test_redis,
        patient_id=7,
        token=token,
    )

    expected = {
        "appointment_id": 42,
        "status": "cancelled",
        "cancelled_at": datetime.now(UTC).isoformat(),
    }

    with patch(
        "optometry.api.agent_confirmations.fetch_cancel_appointment",
        return_value=expected,
    ) as mock_cancel:
        response = client.post(f"/agent/confirmations/{token}/execute/cancel")

        replay = client.post(f"/agent/confirmations/{token}/execute/cancel")

    assert response.status_code == 200
    assert response.json() == expected
    assert replay.status_code == 409

    mock_cancel.assert_called_once()
    assert mock_cancel.call_args.kwargs["patient_id"] == 7
    assert mock_cancel.call_args.kwargs["appointment_id"] == 42


# checks unapproved confirmations cannot execute
def test_execute_requires_approval(
    client: TestClient,
    test_redis: Redis,
) -> None:
    token = prepare_confirmation(
        client=test_redis,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    with patch(
        "optometry.api.agent_confirmations.fetch_cancel_appointment"
    ) as mock_cancel:
        response = client.post(f"/agent/confirmations/{token}/execute/cancel")

    assert response.status_code == 409
    mock_cancel.assert_not_called()


# checks cancellation approval cannot authorize booking
def test_execute_rejects_wrong_action(
    client: TestClient,
    test_redis: Redis,
) -> None:
    token = prepare_confirmation(
        client=test_redis,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=test_redis,
        patient_id=7,
        token=token,
    )

    with patch("optometry.api.agent_confirmations.fetch_book_appointment") as mock_book:
        response = client.post(f"/agent/confirmations/{token}/execute/book")

    assert response.status_code == 409
    mock_book.assert_not_called()

    # wrong-action attempts must not consume the valid approval
    with patch(
        "optometry.api.agent_confirmations.fetch_cancel_appointment",
        return_value={"appointment_id": 42, "status": "cancelled"},
    ):
        correct = client.post(f"/agent/confirmations/{token}/execute/cancel")

    assert correct.status_code == 200


# checks booking proposals are independently validated
def test_prepare_agent_booking_proposal(
    client: TestClient,
    test_redis: Redis,
) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    with patch(
        "optometry.api.agent_confirmations.get_availability",
        return_value=(
            Decimal("95.00"),
            [SimpleNamespace(start=start)],
        ),
    ) as mock_availability:
        response = client.post(
            "/agent/confirmations/prepare",
            json={
                "action": "book",
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": start.isoformat(),
                "requires_confirmation": True,
            },
        )

    assert response.status_code == 200
    data = response.json()

    assert data["action"] == "book"
    assert data["details"]["appointment_price"] == "95.00"
    mock_availability.assert_called_once()

    token = data["confirmation_token"]

    # preparation must not authorize execution
    with pytest.raises(PermissionError):
        consume_confirmation(
            client=test_redis,
            patient_id=7,
            token=token,
            action="book",
        )

    approved = client.post(f"/agent/confirmations/{token}/approve")

    assert approved.status_code == 200

    details = consume_confirmation(
        client=test_redis,
        patient_id=7,
        token=token,
        action="book",
    )

    assert isinstance(details, BookingDetails)
    assert details.appointment_price == Decimal("95.00")


# checks unavailable proposed slots are rejected
def test_prepare_agent_booking_rejects_unavailable_slot(
    client: TestClient,
) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    with patch(
        "optometry.api.agent_confirmations.get_availability",
        return_value=(Decimal("95.00"), []),
    ):
        response = client.post(
            "/agent/confirmations/prepare",
            json={
                "action": "book",
                "clinic_id": 1,
                "optometrist_id": 2,
                "service_id": 3,
                "start_at": start.isoformat(),
                "requires_confirmation": True,
            },
        )

    assert response.status_code == 409


# checks cancellation proposals retain patient ownership
def test_prepare_agent_cancellation_proposal(
    client: TestClient,
) -> None:
    appointment = SimpleNamespace(
        id=42,
        status="booked",
        start_at=datetime.now(UTC) + timedelta(days=7),
    )

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        return_value=appointment,
    ) as mock_get:
        response = client.post(
            "/agent/confirmations/prepare",
            json={
                "action": "cancel",
                "appointment_id": 42,
                "requires_confirmation": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["action"] == "cancel"

    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["patient_id"] == 7


# checks an unowned appointment cannot be prepared
def test_prepare_agent_cancellation_rejects_unowned_appointment(
    client: TestClient,
) -> None:
    from fastapi import HTTPException

    with patch(
        "optometry.api.agent_confirmations.get_appointment",
        side_effect=HTTPException(
            status_code=404,
            detail="Appointment not found",
        ),
    ):
        response = client.post(
            "/agent/confirmations/prepare",
            json={
                "action": "cancel",
                "appointment_id": 999,
                "requires_confirmation": True,
            },
        )

    assert response.status_code == 404
