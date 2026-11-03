"""SQLAlchemy engine and database session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from optometry.core.config import get_database_url

# creates the database engine used by sqlalchemy.
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
)

# session factory used to create database connections.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# loads the db record.
def get_db() -> Generator[Session, None, None]:
    """Provide a database session and close it after use."""
    with SessionLocal() as session:
        yield session
