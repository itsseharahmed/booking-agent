"""Integration tests for schedule and service administration."""

from collections.abc import Iterator
from datetime import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.api.schedules import router as schedules_router
from optometry.api.services import router as services_router
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db


@pytest.fixture
def client(test_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(schedules_router)
    app.include_router(services_router)

    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def clinic(test_session: Session) -> Clinic:
    record = Clinic(
        name="Schedule Admin Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
        country="CA",
    )
    test_session.add(record)
    test_session.flush()
    return record


@pytest.fixture
def optometrist(test_session: Session) -> Optometrist:
    record = Optometrist(
        first_name="Schedule",
        last_name="Tester",
    )
    test_session.add(record)
    test_session.flush()
    return record


@pytest.fixture
def schedule(
    test_session: Session,
    clinic: Clinic,
    optometrist: Optometrist,
) -> WorkingSchedule:
    test_session.add(
        OptometristClinic(
            clinic_id=clinic.id,
            optometrist_id=optometrist.id,
        )
    )
    test_session.flush()

    record = WorkingSchedule(
        clinic_id=clinic.id,
        optometrist_id=optometrist.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_active=True,
    )
    test_session.add(record)
    test_session.flush()
    return record


@pytest.fixture
def service(test_session: Session) -> AppointmentService:
    record = AppointmentService(
        name="Schedule Admin Eye Exam",
        description="Test appointment service",
        is_active=True,
    )
    test_session.add(record)
    test_session.flush()
    return record


def test_delete_schedule(
    client: TestClient,
    schedule: WorkingSchedule,
    test_session: Session,
) -> None:
    schedule_id = schedule.id

    response = client.delete(f"/schedules/{schedule_id}")

    assert response.status_code == 204
    assert test_session.get(WorkingSchedule, schedule_id) is None


def test_delete_missing_schedule(client: TestClient) -> None:
    response = client.delete("/schedules/99999999")

    assert response.status_code == 404


def test_deactivate_schedule(
    client: TestClient,
    schedule: WorkingSchedule,
) -> None:
    response = client.patch(
        f"/schedules/{schedule.id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_reactivate_schedule(
    client: TestClient,
    schedule: WorkingSchedule,
) -> None:
    first = client.patch(
        f"/schedules/{schedule.id}",
        json={"is_active": False},
    )
    second = client.patch(
        f"/schedules/{schedule.id}",
        json={"is_active": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is True


def test_reactivate_overlapping_schedule_rejected(
    client: TestClient,
    schedule: WorkingSchedule,
    test_session: Session,
) -> None:
    response = client.patch(
        f"/schedules/{schedule.id}",
        json={"is_active": False},
    )
    assert response.status_code == 200

    other = WorkingSchedule(
        clinic_id=schedule.clinic_id,
        optometrist_id=schedule.optometrist_id,
        day_of_week=schedule.day_of_week,
        start_time=time(10, 0),
        end_time=time(16, 0),
        is_active=True,
    )
    test_session.add(other)
    test_session.flush()

    response = client.patch(
        f"/schedules/{schedule.id}",
        json={"is_active": True},
    )

    assert response.status_code == 409


def test_delete_service(
    client: TestClient,
    service: AppointmentService,
    test_session: Session,
) -> None:
    service_id = service.id

    response = client.delete(f"/services/{service_id}")

    assert response.status_code == 204
    assert test_session.get(AppointmentService, service_id) is None


def test_delete_missing_service(client: TestClient) -> None:
    response = client.delete("/services/99999999")

    assert response.status_code == 404


def test_deactivate_service(
    client: TestClient,
    service: AppointmentService,
) -> None:
    response = client.patch(
        f"/services/{service.id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_reactivate_service(
    client: TestClient,
    service: AppointmentService,
) -> None:
    first = client.patch(
        f"/services/{service.id}",
        json={"is_active": False},
    )
    second = client.patch(
        f"/services/{service.id}",
        json={"is_active": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is True
