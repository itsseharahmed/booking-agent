"""Integration tests for the working-schedule API."""

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db
from optometry.main import app


def override_test_db(test_session: Session):
    """Provide the test database session to API requests."""
    yield test_session


def test_create_schedule(test_session: Session) -> None:
    """Create a valid weekly working shift."""

    optometrist = Optometrist(
        first_name="Alex",
        last_name="Morgan",
    )

    clinic = Clinic(
        name="Schedule API Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add_all([optometrist, clinic])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/schedules",
                json={
                    "optometrist_id": optometrist.id,
                    "clinic_id": clinic.id,
                    "day_of_week": 0,
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                },
            )

        assert response.status_code == 201

        data = response.json()

        assert data["optometrist_id"] == optometrist.id
        assert data["clinic_id"] == clinic.id
        assert data["day_of_week"] == 0
        assert time.fromisoformat(data["start_time"]) == time(9, 0)
        assert time.fromisoformat(data["end_time"]) == time(17, 0)
        assert data["is_active"] is True
        assert isinstance(data["id"], int)

    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def schedule_setup(test_session: Session) -> tuple[int, int, int]:
    """Create one optometrist assigned to two clinics."""

    optometrist = Optometrist(
        first_name="Alex",
        last_name="Morgan",
    )

    first_clinic = Clinic(
        name="First Schedule Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    second_clinic = Clinic(
        name="Second Schedule Clinic",
        address_line1="456 Queen Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2B4",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add_all([optometrist, first_clinic, second_clinic])
    test_session.flush()

    test_session.add_all(
        [
            OptometristClinic(
                optometrist_id=optometrist.id,
                clinic_id=first_clinic.id,
            ),
            OptometristClinic(
                optometrist_id=optometrist.id,
                clinic_id=second_clinic.id,
            ),
        ]
    )
    test_session.flush()

    return optometrist.id, first_clinic.id, second_clinic.id


def test_reject_unassigned_clinic(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Reject schedules at clinics without an assignment."""

    optometrist_id, _, _ = schedule_setup

    unassigned_clinic = Clinic(
        name="Unassigned Schedule Clinic",
        address_line1="789 King Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 1L7",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(unassigned_clinic)
    test_session.flush()

    app.dependency_overrides[get_db] = lambda: test_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/schedules",
                json={
                    "optometrist_id": optometrist_id,
                    "clinic_id": unassigned_clinic.id,
                    "day_of_week": 0,
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                },
            )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_reject_invalid_schedule_time_range(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Reject a shift ending before it starts."""

    optometrist_id, clinic_id, _ = schedule_setup

    app.dependency_overrides[get_db] = lambda: test_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/schedules",
                json={
                    "optometrist_id": optometrist_id,
                    "clinic_id": clinic_id,
                    "day_of_week": 0,
                    "start_time": "17:00:00",
                    "end_time": "09:00:00",
                },
            )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_reject_overlapping_schedule(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Reject overlapping shifts for the same optometrist."""

    optometrist_id, clinic_id, _ = schedule_setup

    test_session.add(
        WorkingSchedule(
            optometrist_id=optometrist_id,
            clinic_id=clinic_id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )
    )
    test_session.flush()

    app.dependency_overrides[get_db] = lambda: test_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/schedules",
                json={
                    "optometrist_id": optometrist_id,
                    "clinic_id": clinic_id,
                    "day_of_week": 0,
                    "start_time": "12:00:00",
                    "end_time": "17:00:00",
                },
            )

        assert response.status_code == 409

    finally:
        app.dependency_overrides.clear()


def test_reject_insufficient_travel_time_api(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Reject less than 60 minutes between different clinics."""

    optometrist_id, first_clinic_id, second_clinic_id = schedule_setup

    test_session.add(
        WorkingSchedule(
            optometrist_id=optometrist_id,
            clinic_id=first_clinic_id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )
    )
    test_session.flush()

    app.dependency_overrides[get_db] = lambda: test_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/schedules",
                json={
                    "optometrist_id": optometrist_id,
                    "clinic_id": second_clinic_id,
                    "day_of_week": 0,
                    "start_time": "13:30:00",
                    "end_time": "17:00:00",
                },
            )

        assert response.status_code == 409

    finally:
        app.dependency_overrides.clear()


def test_list_schedules(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """List schedules and filter by clinic."""

    optometrist_id, first_clinic_id, second_clinic_id = schedule_setup

    test_session.add_all(
        [
            WorkingSchedule(
                optometrist_id=optometrist_id,
                clinic_id=first_clinic_id,
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(12, 0),
            ),
            WorkingSchedule(
                optometrist_id=optometrist_id,
                clinic_id=second_clinic_id,
                day_of_week=1,
                start_time=time(13, 0),
                end_time=time(17, 0),
            ),
        ]
    )
    test_session.flush()

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            all_response = client.get(
                "/schedules",
                params={"optometrist_id": optometrist_id},
            )
            filtered_response = client.get(
                "/schedules",
                params={"clinic_id": first_clinic_id},
            )

        assert all_response.status_code == 200
        assert len(all_response.json()) == 2
        assert filtered_response.status_code == 200
        assert len(filtered_response.json()) == 1
        assert filtered_response.json()[0]["clinic_id"] == first_clinic_id
    finally:
        app.dependency_overrides.clear()


def test_update_schedule(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Update the hours of an existing shift."""

    optometrist_id, clinic_id, _ = schedule_setup

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )
    test_session.add(schedule)
    test_session.flush()
    schedule_id = schedule.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{schedule_id}",
                json={"end_time": "15:00:00"},
            )

        assert response.status_code == 200
        assert time.fromisoformat(response.json()["end_time"]) == time(15, 0)
    finally:
        app.dependency_overrides.clear()


def test_update_schedule_not_found(test_session: Session) -> None:
    """Return 404 for a missing schedule."""

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/schedules/999999",
                json={"end_time": "15:00:00"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_update_schedule_rejects_invalid_time(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    """Reject an update that reverses shift times."""

    optometrist_id, clinic_id, _ = schedule_setup

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )
    test_session.add(schedule)
    test_session.flush()
    schedule_id = schedule.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{schedule_id}",
                json={"start_time": "16:00:00"},
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_update_rejects_overlapping_shift(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    optometrist_id, first_clinic_id, second_clinic_id = schedule_setup

    first = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=first_clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    second = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=second_clinic_id,
        day_of_week=0,
        start_time=time(13, 0),
        end_time=time(17, 0),
    )
    test_session.add_all([first, second])
    test_session.flush()
    second_id = second.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{second_id}",
                json={"start_time": "11:00:00"},
            )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_update_rejects_insufficient_travel_buffer(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    optometrist_id, first_clinic_id, second_clinic_id = schedule_setup

    first = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=first_clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    second = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=second_clinic_id,
        day_of_week=0,
        start_time=time(13, 0),
        end_time=time(17, 0),
    )
    test_session.add_all([first, second])
    test_session.flush()
    second_id = second.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{second_id}",
                json={"start_time": "12:30:00"},
            )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_update_rejects_unassigned_clinic(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    optometrist_id, clinic_id, _ = schedule_setup

    unassigned = Clinic(
        name="Unassigned Update Clinic",
        address_line1="789 King Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 1L7",
        country="CA",
        timezone="America/Toronto",
    )
    test_session.add(unassigned)

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    test_session.add(schedule)
    test_session.flush()

    schedule_id = schedule.id
    unassigned_id = unassigned.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{schedule_id}",
                json={"clinic_id": unassigned_id},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_update_rejects_null_time(
    test_session: Session,
    schedule_setup: tuple[int, int, int],
) -> None:
    optometrist_id, clinic_id, _ = schedule_setup

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    test_session.add(schedule)
    test_session.flush()
    schedule_id = schedule.id

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/schedules/{schedule_id}",
                json={"start_time": None},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
