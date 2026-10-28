"""Verify that committed test data is rolled back after session cleanup."""

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from optometry.db.models.clinic import Clinic


def test_committed_changes_are_rolled_back(test_engine: Engine) -> None:
    """A session commit must not persist beyond the outer transaction."""

    # Open a connection and start an outer transaction.
    with test_engine.connect() as connection:
        outer_transaction = connection.begin()

        session_factory = sessionmaker(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        with session_factory() as session:
            clinic = Clinic(
                name="Transaction Isolation Test Clinic",
                address_line1="123 Test Street",
                city="Toronto",
                province="Ontario",
                postal_code="M5V 2T6",
                country="CA",
                timezone="America/Toronto",
            )

            session.add(clinic)
            session.commit()

            clinic_id = clinic.id

            # The clinic exists inside the current transaction.
            assert session.get(Clinic, clinic_id) is not None

        # Undo all writes, including the session's commit.
        outer_transaction.rollback()

    # Verify the record does not exist on a separate connection.
    with Session(test_engine) as verification_session:
        persisted_clinic = verification_session.scalar(
            select(Clinic).where(Clinic.id == clinic_id)
        )

        assert persisted_clinic is None
