"""Shared fixtures for PostgreSQL integration tests."""

import os
from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from optometry.core.config import PROJECT_ROOT
from tests.database_safety import validate_test_database_name

# Load local development/test settings into the test process.
load_dotenv(PROJECT_ROOT / ".env")


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Connect only to the dedicated PostgreSQL test database."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("TEST_DATABASE_URL must be configured.")

    # Create a connection engine using the test configuration.
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        # Verify the actual database, not just the URL string.
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

        try:
            validate_test_database_name(database_name)
        except ValueError as exc:
            pytest.fail(str(exc))

        yield engine

    finally:
        # Release all database connections after testing.
        engine.dispose()


@pytest.fixture
def test_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Provide a session whose changes are rolled back after each test."""

    # Open a dedicated connection for this test.
    connection = test_engine.connect()

    # Begin an outer transaction that the application cannot commit.
    transaction = connection.begin()

    # SQLAlchemy creates savepoints for session-level transactions.
    session_factory = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    session = session_factory()

    try:
        yield session
    finally:
        session.close()

        # Undo all changes, including changes committed by API endpoints.
        transaction.rollback()
        connection.close()
