"""Integration tests for clinic and optometrist administration."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.api.clinics import router as clinics_router
from optometry.api.optometrists import router as optometrists_router
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import create_admin_access_token, hash_password
from optometry.db.models.admin import Admin
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.session import get_db


# creates the shared test fixture.
@pytest.fixture
# builds the test client used by the test.
def client(test_session: Session) -> Iterator[TestClient]:
    # creates the api application.
    app = FastAPI()
    app.include_router(clinics_router)
    app.include_router(optometrists_router)

    # overrides a dependency during the test.
    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    admin = Admin(
        email="admin-crud-test@example.com",
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


# creates the shared test fixture.
@pytest.fixture
# handles the clinic workflow.
def clinic(test_session: Session) -> Clinic:
    record = Clinic(
        name="Test Eye Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
        country="CA",
    )
    test_session.add(record)
    test_session.flush()
    return record


# creates the shared test fixture.
@pytest.fixture
# handles the optometrist workflow.
def optometrist(test_session: Session) -> Optometrist:
    record = Optometrist(
        first_name="Jane",
        last_name="Smith",
    )
    test_session.add(record)
    test_session.flush()
    return record


# checks that update clinic name works as expected.
def test_update_clinic_name(
    client: TestClient,
    clinic: Clinic,
) -> None:
    response = client.patch(
        f"/clinics/{clinic.id}",
        json={"name": "Updated Eye Clinic"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Eye Clinic"


# checks that deactivate clinic works as expected.
def test_deactivate_clinic(
    client: TestClient,
    clinic: Clinic,
) -> None:
    response = client.patch(
        f"/clinics/{clinic.id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


# checks that reactivate clinic works as expected.
def test_reactivate_clinic(
    client: TestClient,
    clinic: Clinic,
) -> None:
    first = client.patch(
        f"/clinics/{clinic.id}",
        json={"is_active": False},
    )
    second = client.patch(
        f"/clinics/{clinic.id}",
        json={"is_active": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is True


# checks that delete unassigned clinic works as expected.
def test_delete_unassigned_clinic(
    client: TestClient,
    clinic: Clinic,
    test_session: Session,
) -> None:
    clinic_id = clinic.id

    response = client.delete(f"/clinics/{clinic_id}")

    assert response.status_code == 204
    assert test_session.get(Clinic, clinic_id) is None


# checks that delete assigned clinic rejected works as expected.
def test_delete_assigned_clinic_rejected(
    client: TestClient,
    clinic: Clinic,
    optometrist: Optometrist,
    test_session: Session,
) -> None:
    test_session.add(
        OptometristClinic(
            clinic_id=clinic.id,
            optometrist_id=optometrist.id,
        )
    )
    test_session.flush()

    response = client.delete(f"/clinics/{clinic.id}")

    assert response.status_code == 409
    assert test_session.get(Clinic, clinic.id) is not None


# checks that update missing clinic works as expected.
def test_update_missing_clinic(client: TestClient) -> None:
    response = client.patch(
        "/clinics/99999999",
        json={"name": "Missing Clinic"},
    )

    assert response.status_code == 404


# checks that delete missing clinic works as expected.
def test_delete_missing_clinic(client: TestClient) -> None:
    response = client.delete("/clinics/99999999")

    assert response.status_code == 404


# checks that reject null clinic name works as expected.
def test_reject_null_clinic_name(
    client: TestClient,
    clinic: Clinic,
) -> None:
    response = client.patch(
        f"/clinics/{clinic.id}",
        json={"name": None},
    )

    assert response.status_code == 422


# checks that reject empty clinic update works as expected.
def test_reject_empty_clinic_update(
    client: TestClient,
    clinic: Clinic,
) -> None:
    response = client.patch(
        f"/clinics/{clinic.id}",
        json={},
    )

    assert response.status_code == 422


# checks that update optometrist name works as expected.
def test_update_optometrist_name(
    client: TestClient,
    optometrist: Optometrist,
) -> None:
    response = client.patch(
        f"/optometrists/{optometrist.id}",
        json={"first_name": "Janet"},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Janet"


# checks that deactivate optometrist works as expected.
def test_deactivate_optometrist(
    client: TestClient,
    optometrist: Optometrist,
) -> None:
    response = client.patch(
        f"/optometrists/{optometrist.id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


# checks that reactivate optometrist works as expected.
def test_reactivate_optometrist(
    client: TestClient,
    optometrist: Optometrist,
) -> None:
    first = client.patch(
        f"/optometrists/{optometrist.id}",
        json={"is_active": False},
    )
    second = client.patch(
        f"/optometrists/{optometrist.id}",
        json={"is_active": True},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is True


# checks that delete unassigned optometrist works as expected.
def test_delete_unassigned_optometrist(
    client: TestClient,
    optometrist: Optometrist,
    test_session: Session,
) -> None:
    optometrist_id = optometrist.id

    response = client.delete(f"/optometrists/{optometrist_id}")

    assert response.status_code == 204
    assert test_session.get(Optometrist, optometrist_id) is None


# checks that delete assigned optometrist rejected works as expected.
def test_delete_assigned_optometrist_rejected(
    client: TestClient,
    clinic: Clinic,
    optometrist: Optometrist,
    test_session: Session,
) -> None:
    test_session.add(
        OptometristClinic(
            clinic_id=clinic.id,
            optometrist_id=optometrist.id,
        )
    )
    test_session.flush()

    response = client.delete(f"/optometrists/{optometrist.id}")

    assert response.status_code == 409
    assert test_session.get(Optometrist, optometrist.id) is not None


# checks that update missing optometrist works as expected.
def test_update_missing_optometrist(
    client: TestClient,
) -> None:
    response = client.patch(
        "/optometrists/99999999",
        json={"first_name": "Missing"},
    )

    assert response.status_code == 404


# checks that delete missing optometrist works as expected.
def test_delete_missing_optometrist(
    client: TestClient,
) -> None:
    response = client.delete("/optometrists/99999999")

    assert response.status_code == 404


# checks that reject null optometrist name works as expected.
def test_reject_null_optometrist_name(
    client: TestClient,
    optometrist: Optometrist,
) -> None:
    response = client.patch(
        f"/optometrists/{optometrist.id}",
        json={"first_name": None},
    )

    assert response.status_code == 422


# checks that reject empty optometrist update works as expected.
def test_reject_empty_optometrist_update(
    client: TestClient,
    optometrist: Optometrist,
) -> None:
    response = client.patch(
        f"/optometrists/{optometrist.id}",
        json={},
    )

    assert response.status_code == 422
