"""Integration tests for PostgreSQL connectivity and sessions."""

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


# checks that database connection works as expected.
def test_database_connection(test_engine: Engine) -> None:
    """Verify that the test database accepts SQL queries."""
    with test_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


# checks that session uses test database works as expected.
def test_session_uses_test_database(test_session: Session) -> None:
    """Verify the session is connected to the isolated test database."""

    database_name = test_session.execute(text("SELECT current_database()")).scalar_one()

    assert database_name == "optometry_booking_test"


# checks that session rollback works as expected.
def test_session_rollback(test_session: Session) -> None:
    """Verify that an uncommitted transaction can be rolled back."""

    # create a temporary table scoped to this transaction.
    test_session.execute(text("CREATE TEMP TABLE rollback_check (id INTEGER)"))

    test_session.execute(text("INSERT INTO rollback_check (id) VALUES (1)"))

    # undo the current transaction.
    test_session.rollback()

    # confirm the transaction has ended.
    assert not test_session.in_transaction()
