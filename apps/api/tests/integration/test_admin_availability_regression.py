"""Regression tests for administrative changes and appointment availability."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.api.availability import router as availability_router
from optometry.api.clinics import router as clinics_router
from optometry.api.optometrists import router as optometrists_router
from optometry.api.schedules import router as schedules_router
from optometry.api.services import router as services_router
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import create_admin_access_token, hash_password
from optometry.db.models.admin import Admin
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.patient import Patient
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db


@pytest.fixture
def client(test_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(availability_router)
    app.include_router(clinics_router)
    app.include_router(optometrists_router)
    app.include_router(schedules_router)
    app.include_router(services_router)

    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db
    admin = Admin(
        email="availability-admin@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )
    test_session.add(admin)
    test_session.flush()

    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def setup_data(test_session: Session) -> dict[str, int | date]:
    clinic = Clinic(
        name="Regression Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
        country="CA",
        appointment_price=Decimal("95.00"),
    )
    doctor = Optometrist(
        first_name="Regression",
        last_name="Doctor",
    )
    service = AppointmentService(
        name="Regression Eye Examination",
        is_active=True,
    )

    test_session.add_all([clinic, doctor, service])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            clinic_id=clinic.id,
            optometrist_id=doctor.id,
        )
    )

    # Use a future Monday so the weekday matches the schedule.
    today = datetime.now(UTC).date()
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7

    appointment_date = today + timedelta(days=days_until_monday)

    schedule = WorkingSchedule(
        clinic_id=clinic.id,
        optometrist_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
        is_active=True,
    )

    test_session.add(schedule)
    test_session.flush()

    return {
        "clinic_id": clinic.id,
        "doctor_id": doctor.id,
        "service_id": service.id,
        "schedule_id": schedule.id,
        "appointment_date": appointment_date,
    }


def availability(
    client: TestClient,
    data: dict[str, int | date],
):
    return client.get(
        "/availability",
        params={
            "clinic_id": data["clinic_id"],
            "optometrist_id": data["doctor_id"],
            "service_id": data["service_id"],
            "appointment_date": str(data["appointment_date"]),
        },
    )


@pytest.mark.parametrize(
    ("resource", "id_key"),
    [
        ("clinics", "clinic_id"),
        ("optometrists", "doctor_id"),
        ("schedules", "schedule_id"),
        ("services", "service_id"),
    ],
)
def test_deactivation_removes_availability(
    client: TestClient,
    setup_data: dict[str, int | date],
    resource: str,
    id_key: str,
) -> None:
    before = availability(client, setup_data)

    assert before.status_code == 200
    assert len(before.json()["slots"]) > 0

    response = client.patch(
        f"/{resource}/{setup_data[id_key]}",
        json={"is_active": False},
    )
    assert response.status_code == 200

    after = availability(client, setup_data)

    assert after.status_code == 200
    assert after.json()["slots"] == []


@pytest.mark.parametrize(
    ("resource", "id_key"),
    [
        ("clinics", "clinic_id"),
        ("optometrists", "doctor_id"),
        ("schedules", "schedule_id"),
        ("services", "service_id"),
    ],
)
def test_reactivation_restores_availability(
    client: TestClient,
    setup_data: dict[str, int | date],
    resource: str,
    id_key: str,
) -> None:
    resource_id = setup_data[id_key]

    deactivated = client.patch(
        f"/{resource}/{resource_id}",
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    inactive = availability(client, setup_data)
    assert inactive.status_code == 200
    assert inactive.json()["slots"] == []

    reactivated = client.patch(
        f"/{resource}/{resource_id}",
        json={"is_active": True},
    )
    assert reactivated.status_code == 200

    restored = availability(client, setup_data)
    assert restored.status_code == 200
    assert len(restored.json()["slots"]) > 0


def test_schedule_deletion_removes_availability(
    client: TestClient,
    setup_data: dict[str, int | date],
) -> None:
    before = availability(client, setup_data)
    assert before.status_code == 200
    assert len(before.json()["slots"]) > 0

    response = client.delete(f"/schedules/{setup_data['schedule_id']}")
    assert response.status_code == 204

    after = availability(client, setup_data)
    assert after.status_code == 200
    assert after.json()["slots"] == []


def test_existing_appointment_survives_deactivation(
    client: TestClient,
    setup_data: dict[str, int | date],
    test_session: Session,
) -> None:
    patient = Patient(
        first_name="History",
        last_name="Patient",
        email="history-patient@example.com",
        password_hash="test-only-placeholder",
    )
    test_session.add(patient)
    test_session.flush()

    appointment_day = setup_data["appointment_date"]
    assert isinstance(appointment_day, date)

    start = datetime.combine(
        appointment_day,
        time(14, 0),
        tzinfo=UTC,
    )

    appointment = Appointment(
        patient_id=patient.id,
        clinic_id=setup_data["clinic_id"],
        optometrist_id=setup_data["doctor_id"],
        service_id=setup_data["service_id"],
        start_at=start,
        end_at=start + timedelta(minutes=20),
        status="booked",
        appointment_price=Decimal("95.00"),
    )

    test_session.add(appointment)
    test_session.flush()
    appointment_id = appointment.id

    response = client.patch(
        f"/clinics/{setup_data['clinic_id']}",
        json={"is_active": False},
    )
    assert response.status_code == 200

    persisted = test_session.get(Appointment, appointment_id)

    assert persisted is not None
    assert persisted.status == "booked"
    assert persisted.appointment_price == Decimal("95.00")


def test_existing_appointment_survives_schedule_deletion(
    client: TestClient,
    setup_data: dict[str, int | date],
    test_session: Session,
) -> None:
    appointment_day = setup_data["appointment_date"]
    assert isinstance(appointment_day, date)

    start = datetime.combine(
        appointment_day,
        time(14, 0),
        tzinfo=UTC,
    )

    appointment = Appointment(
        clinic_id=setup_data["clinic_id"],
        optometrist_id=setup_data["doctor_id"],
        service_id=setup_data["service_id"],
        start_at=start,
        end_at=start + timedelta(minutes=20),
        status="booked",
        appointment_price=Decimal("95.00"),
    )

    test_session.add(appointment)
    test_session.flush()
    appointment_id = appointment.id

    response = client.delete(f"/schedules/{setup_data['schedule_id']}")
    assert response.status_code == 204

    persisted = test_session.get(Appointment, appointment_id)

    assert persisted is not None
    assert persisted.status == "booked"


def test_service_with_appointment_cannot_be_deleted(
    client: TestClient,
    setup_data: dict[str, int | date],
    test_session: Session,
) -> None:
    appointment_day = setup_data["appointment_date"]
    assert isinstance(appointment_day, date)

    start = datetime.combine(
        appointment_day,
        time(14, 0),
        tzinfo=UTC,
    )

    appointment = Appointment(
        clinic_id=setup_data["clinic_id"],
        optometrist_id=setup_data["doctor_id"],
        service_id=setup_data["service_id"],
        start_at=start,
        end_at=start + timedelta(minutes=20),
        status="booked",
        appointment_price=Decimal("95.00"),
    )

    test_session.add(appointment)
    test_session.flush()

    response = client.delete(f"/services/{setup_data['service_id']}")

    assert response.status_code == 409
    assert (
        test_session.get(
            AppointmentService,
            setup_data["service_id"],
        )
        is not None
    )
