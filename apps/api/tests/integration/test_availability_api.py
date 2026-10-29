"""Integration tests for appointment availability."""

from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db
from optometry.main import app


@pytest.fixture
def client(test_session: Session):
    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def availability_data(test_session: Session):
    clinic = Clinic(
        name="Availability Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price="120.00",
    )
    optometrist = Optometrist(
        first_name="Availability",
        last_name="Tester",
    )
    service = AppointmentService(
        name="Availability Eye Exam",
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

    appointment_date = datetime.now(UTC).date() + timedelta(days=14)

    test_session.add(
        WorkingSchedule(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
            day_of_week=appointment_date.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
    )
    test_session.flush()

    return {
        "clinic": clinic,
        "optometrist": optometrist,
        "service": service,
        "date": appointment_date,
    }


def availability_params(data):
    return {
        "clinic_id": data["clinic"].id,
        "optometrist_id": data["optometrist"].id,
        "service_id": data["service"].id,
        "appointment_date": data["date"].isoformat(),
    }


def test_returns_available_slots(client, availability_data):
    response = client.get(
        "/availability",
        params=availability_params(availability_data),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["duration_minutes"] == 20
    assert body["timezone"] == "America/Toronto"
    assert body["appointment_price"] == "120.00"
    assert len(body["slots"]) == 3
    assert body["slots"][0]["start"].endswith("09:00:00-05:00") or (
        body["slots"][0]["start"].endswith("09:00:00-04:00")
    )


def test_inactive_clinic_returns_no_slots(client, test_session, availability_data):
    availability_data["clinic"].is_active = False
    test_session.flush()

    response = client.get(
        "/availability",
        params=availability_params(availability_data),
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_inactive_optometrist_returns_no_slots(client, test_session, availability_data):
    availability_data["optometrist"].is_active = False
    test_session.flush()

    response = client.get(
        "/availability",
        params=availability_params(availability_data),
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_inactive_service_returns_no_slots(client, test_session, availability_data):
    availability_data["service"].is_active = False
    test_session.flush()

    response = client.get(
        "/availability",
        params=availability_params(availability_data),
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_inactive_schedule_returns_no_slots(client, test_session, availability_data):
    schedule = (
        test_session.query(WorkingSchedule)
        .filter_by(clinic_id=availability_data["clinic"].id)
        .one()
    )
    schedule.is_active = False
    test_session.flush()

    response = client.get(
        "/availability",
        params=availability_params(availability_data),
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_missing_clinic_returns_404(client, availability_data):
    params = availability_params(availability_data)
    params["clinic_id"] = 999999

    response = client.get("/availability", params=params)

    assert response.status_code == 404


def test_missing_service_returns_404(client, availability_data):
    params = availability_params(availability_data)
    params["service_id"] = 999999

    response = client.get("/availability", params=params)

    assert response.status_code == 404


def test_invalid_ids_return_422(client):
    response = client.get(
        "/availability",
        params={
            "clinic_id": -1,
            "optometrist_id": 0,
            "service_id": -1,
            "appointment_date": "2026-11-02",
        },
    )

    assert response.status_code == 422


def test_missing_parameters_return_422(client):
    response = client.get("/availability")

    assert response.status_code == 422


def test_missing_optometrist_returns_404(client, availability_data):
    params = availability_params(availability_data)
    params["optometrist_id"] = 999999

    response = client.get("/availability", params=params)

    assert response.status_code == 404


def test_unassigned_optometrist_returns_no_slots(
    client, test_session, availability_data
):
    # Create an optometrist who is not assigned to the clinic.
    unassigned = Optometrist(
        first_name="Unassigned",
        last_name="Optometrist",
    )

    test_session.add(unassigned)
    test_session.flush()

    params = availability_params(availability_data)
    params["optometrist_id"] = unassigned.id

    response = client.get(
        "/availability",
        params=params,
    )

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_day_without_schedule_returns_no_slots(client, availability_data):
    params = availability_params(availability_data)
    params["appointment_date"] = (
        availability_data["date"] + timedelta(days=1)
    ).isoformat()

    response = client.get("/availability", params=params)

    assert response.status_code == 200
    assert response.json()["slots"] == []


def test_past_date_returns_no_slots(client, availability_data):
    params = availability_params(availability_data)
    params["appointment_date"] = "2020-01-01"

    response = client.get("/availability", params=params)

    assert response.status_code == 200
    assert response.json()["slots"] == []
