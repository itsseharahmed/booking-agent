"""Integration tests for the optometrist API."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.session import get_db
from optometry.main import app


def test_create_optometrist(test_session: Session) -> None:
    """Create an optometrist through the API."""

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/optometrists",
                json={
                    "first_name": "Alex",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

        assert response.status_code == 201

        data = response.json()

        assert data["first_name"] == "Alex"
        assert data["last_name"] == "Morgan"
        assert data["license_number"] == "TEST-12345"
        assert data["is_active"] is True
        assert isinstance(data["id"], int)

    finally:
        app.dependency_overrides.clear()


def test_reject_optometrist_with_whitespace_only_name(
    test_session: Session,
) -> None:
    """Reject optometrist names containing only whitespace."""

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/optometrists",
                json={
                    "first_name": "   ",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_list_optometrists(test_session: Session) -> None:
    """Retrieve optometrists through the API."""

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/optometrists",
                json={
                    "first_name": "Alex",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

            assert create_response.status_code == 201
            created_id = create_response.json()["id"]

            response = client.get("/optometrists")

        assert response.status_code == 200

        data = response.json()

        assert isinstance(data, list)
        assert any(
            optometrist["id"] == created_id
            and optometrist["first_name"] == "Alex"
            and optometrist["last_name"] == "Morgan"
            for optometrist in data
        )

    finally:
        app.dependency_overrides.clear()


def test_assign_optometrist_to_clinic(
    test_session: Session,
) -> None:
    """Assign an optometrist to an existing clinic."""

    clinic = Clinic(
        name="Assignment Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(clinic)
    test_session.flush()

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/optometrists",
                json={
                    "first_name": "Alex",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

            assert create_response.status_code == 201
            optometrist_id = create_response.json()["id"]

            response = client.post(
                f"/optometrists/{optometrist_id}/clinics",
                json={"clinic_id": clinic.id},
            )

        assert response.status_code == 201
        assert response.json() == {
            "optometrist_id": optometrist_id,
            "clinic_id": clinic.id,
        }

    finally:
        app.dependency_overrides.clear()


def test_reject_duplicate_clinic_assignment(
    test_session: Session,
) -> None:
    """An optometrist cannot be assigned to the same clinic twice."""

    clinic = Clinic(
        name="Duplicate Assignment Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(clinic)
    test_session.flush()

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/optometrists",
                json={
                    "first_name": "Alex",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

            assert create_response.status_code == 201
            optometrist_id = create_response.json()["id"]

            assignment_url = f"/optometrists/{optometrist_id}/clinics"

            first_response = client.post(
                assignment_url,
                json={"clinic_id": clinic.id},
            )

            second_response = client.post(
                assignment_url,
                json={"clinic_id": clinic.id},
            )

        assert first_response.status_code == 201
        assert second_response.status_code == 409
        assert second_response.json()["detail"] == (
            "Optometrist is already assigned to this clinic"
        )

    finally:
        app.dependency_overrides.clear()


def test_reject_assignment_to_nonexistent_optometrist(
    test_session: Session,
) -> None:
    """Return 404 when the optometrist does not exist."""

    clinic = Clinic(
        name="Assignment Validation Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(clinic)
    test_session.flush()

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/optometrists/999999/clinics",
                json={"clinic_id": clinic.id},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Optometrist not found"

    finally:
        app.dependency_overrides.clear()


def test_reject_assignment_to_nonexistent_clinic(
    test_session: Session,
) -> None:
    """Return 404 when the clinic does not exist."""

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/optometrists",
                json={
                    "first_name": "Alex",
                    "last_name": "Morgan",
                    "license_number": "TEST-12345",
                },
            )

            assert create_response.status_code == 201
            optometrist_id = create_response.json()["id"]

            response = client.post(
                f"/optometrists/{optometrist_id}/clinics",
                json={"clinic_id": 999999},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Clinic not found"

    finally:
        app.dependency_overrides.clear()
