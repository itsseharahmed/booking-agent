"""Integration tests for admin clinic knowledge."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from optometry.api.admin_clinic_knowledge import router
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import (
    create_admin_access_token,
    hash_password,
)
from optometry.db.models.admin import Admin
from optometry.db.models.clinic import Clinic
from optometry.db.models.clinic_knowledge import ClinicKnowledge
from optometry.db.session import get_db


@pytest.fixture
def admin_client(test_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)

    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    admin = Admin(
        email=f"knowledge-{uuid4().hex}@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )
    test_session.add(admin)
    test_session.flush()

    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )

    with TestClient(app) as client:
        client.headers.update(
            {
                "Authorization": f"Bearer {token}",
            }
        )
        yield client


@pytest.fixture
def clinic(test_session: Session) -> Clinic:
    record = Clinic(
        name="Knowledge Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
        country="CA",
    )
    test_session.add(record)
    test_session.flush()
    return record


def test_admin_creates_and_reads_knowledge(
    admin_client: TestClient,
    clinic: Clinic,
) -> None:
    payload = {
        "insurance_info": "Sun Life accepted",
        "parking_info": "Free parking",
        "accessibility_info": "Wheelchair accessible",
        "appointment_policy": "24-hour cancellation notice",
        "additional_info": "Saturday appointments available",
    }

    response = admin_client.put(
        f"/admin/clinics/{clinic.id}/knowledge",
        json=payload,
    )

    assert response.status_code == 200, response.text
    assert response.json()["clinic_id"] == clinic.id
    assert response.json()["insurance_info"] == "Sun Life accepted"

    read_response = admin_client.get(f"/admin/clinics/{clinic.id}/knowledge")

    assert read_response.status_code == 200
    assert read_response.json()["parking_info"] == "Free parking"


def test_admin_updates_existing_knowledge(
    admin_client: TestClient,
    test_session: Session,
    clinic: Clinic,
) -> None:
    test_session.add(
        ClinicKnowledge(
            clinic_id=clinic.id,
            insurance_info="Old insurance information",
        )
    )
    test_session.flush()

    response = admin_client.put(
        f"/admin/clinics/{clinic.id}/knowledge",
        json={"insurance_info": "Updated insurance information"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["insurance_info"] == ("Updated insurance information")

    test_session.expire_all()

    record = test_session.get(ClinicKnowledge, clinic.id)
    assert record is not None
    assert record.insurance_info == "Updated insurance information"


def test_missing_clinic_returns_404(
    admin_client: TestClient,
) -> None:
    response = admin_client.put(
        "/admin/clinics/999999/knowledge",
        json={"parking_info": "Free parking"},
    )

    assert response.status_code == 404


def test_excessive_text_is_rejected(
    admin_client: TestClient,
    clinic: Clinic,
) -> None:
    response = admin_client.put(
        f"/admin/clinics/{clinic.id}/knowledge",
        json={"insurance_info": "x" * 2001},
    )

    assert response.status_code == 422


def test_unauthenticated_access_is_rejected(
    test_session: Session,
    clinic: Clinic,
) -> None:
    app = FastAPI()
    app.include_router(router)

    def override_db() -> Iterator[Session]:
        yield test_session

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        read_response = client.get(f"/admin/clinics/{clinic.id}/knowledge")
        write_response = client.put(
            f"/admin/clinics/{clinic.id}/knowledge",
            json={"insurance_info": "Unauthorized update"},
        )

    assert read_response.status_code == 401
    assert write_response.status_code == 401
