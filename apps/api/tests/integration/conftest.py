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
    """Provide a session connected exclusively to the test database."""

    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as session:
        yield session
        session.rollback()
