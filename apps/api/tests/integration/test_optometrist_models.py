"""Integration tests for optometrists and clinic assignments."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic


def test_create_optometrist(test_session: Session) -> None:
    """An optometrist can be saved and retrieved."""

    optometrist = Optometrist(
        first_name="Alex",
        last_name="Morgan",
        license_number="TEST-12345",
    )

    test_session.add(optometrist)
    test_session.flush()
    test_session.refresh(optometrist)

    saved = test_session.scalar(
        select(Optometrist).where(Optometrist.id == optometrist.id)
    )

    assert saved is not None
    assert saved.first_name == "Alex"
    assert saved.last_name == "Morgan"
    assert saved.is_active is True
    assert saved.created_at is not None


def test_assign_optometrist_to_multiple_clinics(
    test_session: Session,
) -> None:
    """One optometrist can work at multiple clinic locations."""

    optometrist = Optometrist(
        first_name="Alex",
        last_name="Morgan",
    )

    clinic_a = Clinic(
        name="Downtown Vision",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    clinic_b = Clinic(
        name="Uptown Vision",
        address_line1="456 Yonge Street",
        city="Toronto",
        province="Ontario",
        postal_code="M4W 2G8",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add_all([optometrist, clinic_a, clinic_b])
    test_session.flush()

    test_session.add_all(
        [
            OptometristClinic(
                optometrist_id=optometrist.id,
                clinic_id=clinic_a.id,
            ),
            OptometristClinic(
                optometrist_id=optometrist.id,
                clinic_id=clinic_b.id,
            ),
        ]
    )
    test_session.flush()

    assignments = test_session.scalars(
        select(OptometristClinic).where(
            OptometristClinic.optometrist_id == optometrist.id
        )
    ).all()

    assert len(assignments) == 2
    assert {a.clinic_id for a in assignments} == {
        clinic_a.id,
        clinic_b.id,
    }
