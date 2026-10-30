"""Booking API integration tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from optometry.api.appointments import router as appointments_router
from optometry.api.availability import router as availability_router
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db


@pytest.fixture
def client(test_session):
    app = FastAPI()
    app.include_router(appointments_router)
    app.include_router(availability_router)

    def override_db():
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def booking_data(test_session):
    clinic = Clinic(
        name="Booking API Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("95.00"),
    )
    optometrist = Optometrist(
        first_name="API",
        last_name="Booking",
    )
    service = AppointmentService(
        name="Booking API Eye Exam",
    )

    test_session.add_all([clinic, optometrist, service])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    # Find a future Monday so day_of_week=0 is predictable.
    target = datetime.now(UTC).date() + timedelta(days=21)
    target += timedelta(days=(0 - target.weekday()) % 7)

    test_session.add(
        WorkingSchedule(
            clinic_id=clinic.id,
            optometrist_id=optometrist.id,
            day_of_week=0,
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("10:00", "%H:%M").time(),
            is_active=True,
        )
    )
    test_session.flush()

    return {
        "clinic_id": clinic.id,
        "optometrist_id": optometrist.id,
        "service_id": service.id,
        "appointment_date": target.isoformat(),
    }


def availability_params(data):
    return {
        "clinic_id": data["clinic_id"],
        "optometrist_id": data["optometrist_id"],
        "service_id": data["service_id"],
        "appointment_date": data["appointment_date"],
    }


def first_available_slot(client, data):
    response = client.get(
        "/availability",
        params=availability_params(data),
    )
    assert response.status_code == 200
    slots = response.json()["slots"]
    assert slots
    return slots[0]


def booking_payload(data, slot):
    return {
        "clinic_id": data["clinic_id"],
        "optometrist_id": data["optometrist_id"],
        "service_id": data["service_id"],
        "start_at": slot["start"],
    }


def test_create_booking(client, booking_data):
    slot = first_available_slot(client, booking_data)

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "booked"
    assert Decimal(result["appointment_price"]) == Decimal("95.00")
    assert result["start_at"] is not None
    assert result["end_at"] is not None


def test_booking_removes_slot_from_availability(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    response = client.get(
        "/availability",
        params=availability_params(booking_data),
    )
    assert response.status_code == 200

    starts = [item["start"] for item in response.json()["slots"]]
    assert slot["start"] not in starts


def test_duplicate_booking_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    second = client.post("/appointments", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_cancel_booking_restores_slot(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]

    cancelled = client.post(f"/appointments/{appointment_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None

    response = client.get(
        "/availability",
        params=availability_params(booking_data),
    )

    starts = [item["start"] for item in response.json()["slots"]]
    assert slot["start"] in starts


def test_cancel_twice_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    appointment_id = created.json()["id"]

    first = client.post(f"/appointments/{appointment_id}/cancel")
    second = client.post(f"/appointments/{appointment_id}/cancel")

    assert first.status_code == 200
    assert second.status_code == 409


def test_booking_invalid_slot_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    invalid_start = datetime.fromisoformat(slot["start"]) + timedelta(minutes=5)

    payload = booking_payload(booking_data, slot)
    payload["start_at"] = invalid_start.isoformat()

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


def test_get_booking(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    appointment_id = created.json()["id"]

    response = client.get(f"/appointments/{appointment_id}")

    assert response.status_code == 200
    assert response.json()["id"] == appointment_id


def test_list_bookings(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    response = client.get(
        "/appointments",
        params={"clinic_id": booking_data["clinic_id"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_missing_booking_returns_404(client):
    response = client.get("/appointments/99999999")
    assert response.status_code == 404


def test_naive_datetime_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    payload["start_at"] = (
        datetime.fromisoformat(slot["start"]).replace(tzinfo=None).isoformat()
    )

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


def test_booking_price_is_snapshot(client, test_session, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]
    original_price = Decimal(created.json()["appointment_price"])

    clinic = test_session.get(Clinic, booking_data["clinic_id"])
    assert clinic is not None

    clinic.appointment_price = Decimal("150.00")
    test_session.flush()

    response = client.get(f"/appointments/{appointment_id}")

    assert response.status_code == 200
    assert Decimal(response.json()["appointment_price"]) == original_price


def test_cancelled_booking_stays_in_history(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]

    cancelled = client.post(f"/appointments/{appointment_id}/cancel")
    assert cancelled.status_code == 200

    response = client.get(
        "/appointments",
        params={
            "clinic_id": booking_data["clinic_id"],
            "status": "cancelled",
        },
    )

    assert response.status_code == 200
    assert any(item["id"] == appointment_id for item in response.json())


def test_rebooking_after_cancellation(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    assert first.status_code == 201

    cancelled = client.post(f"/appointments/{first.json()['id']}/cancel")
    assert cancelled.status_code == 200

    replacement = client.post("/appointments", json=payload)

    assert replacement.status_code == 201
    assert replacement.json()["id"] != first.json()["id"]


def test_occupied_slot_is_conflict_not_invalid_time(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    assert first.status_code == 201

    second = client.post("/appointments", json=payload)

    assert second.status_code == 409


def test_booking_outside_working_hours_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)

    outside_start = datetime.fromisoformat(slot["start"]) - timedelta(minutes=20)

    payload = booking_payload(booking_data, slot)
    payload["start_at"] = outside_start.isoformat()

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


def test_booking_with_inactive_service_rejected(client, test_session, booking_data):
    slot = first_available_slot(client, booking_data)

    service = test_session.get(
        AppointmentService,
        booking_data["service_id"],
    )
    assert service is not None

    service.is_active = False
    test_session.flush()

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 422


def test_cancel_missing_booking_returns_404(client):
    response = client.post("/appointments/99999999/cancel")
    assert response.status_code == 404


def test_appointment_interval_is_twenty_minutes(client, booking_data):
    slot = first_available_slot(client, booking_data)

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 201

    start = datetime.fromisoformat(response.json()["start_at"])
    end = datetime.fromisoformat(response.json()["end_at"])

    assert end - start == timedelta(minutes=20)
