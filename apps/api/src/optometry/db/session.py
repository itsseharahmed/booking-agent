"""SQLAlchemy engine and database session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from optometry.core.config import get_database_url

# The engine manages a pool of PostgreSQL connections.
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
)

# Factory for creating independent database sessions.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and close it after use."""
    with SessionLocal() as session:
        yield session
