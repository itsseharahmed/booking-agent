"""Shared fixtures for PostgreSQL integration tests."""

import os
from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from redis import Redis
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from optometry.core.config import PROJECT_ROOT, get_jwt_secret_key, get_test_redis_url
from optometry.core.security import create_admin_access_token, hash_password
from optometry.db.models.admin import Admin
from tests.database_safety import validate_test_database_name

# load local development/test settings into the test process.
load_dotenv(PROJECT_ROOT / ".env")


# creates the shared test fixture.
@pytest.fixture(scope="session")
# checks that engine works as expected.
def test_engine() -> Generator[Engine, None, None]:
    """Connect only to the dedicated PostgreSQL test database."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("TEST_DATABASE_URL must be configured.")

    # creates the database engine used by sqlalchemy.
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        # verify the actual database, not just the URL string.
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
        # release all database connections after testing.
        engine.dispose()


# creates the shared test fixture.
@pytest.fixture
# checks that session works as expected.
def test_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Provide a session whose changes are rolled back after each test."""

    # open a dedicated connection for this test.
    connection = test_engine.connect()

    # begin an outer transaction that the application cannot commit.
    transaction = connection.begin()

    # sQLAlchemy creates savepoints for session-level transactions.
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

        # undo all changes, including changes committed by API endpoints.
        transaction.rollback()
        connection.close()


# creates the shared test fixture.
@pytest.fixture
# handles the admin auth headers workflow.
def admin_auth_headers(
    test_session: Session,
) -> dict[str, str]:
    """Create a test administrator and return its authorization header."""
    admin = Admin(
        email="crud-admin@example.com",
        password_hash=hash_password("SecurePassword123!"),
        is_active=True,
    )
    test_session.add(admin)
    test_session.flush()

    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )

    return {"Authorization": f"Bearer {token}"}


# provides an isolated redis client for integration tests
@pytest.fixture
def test_redis() -> Generator[Redis, None, None]:
    client = Redis.from_url(
        get_test_redis_url(),
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )

    if client.connection_pool.connection_kwargs.get("db") != 1:
        pytest.fail("Tests must use Redis database 1")

    try:
        client.ping()
        client.flushdb()
        yield client
    finally:
        client.flushdb()
        client.close()
