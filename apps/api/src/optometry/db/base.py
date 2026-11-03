"""Shared declarative base for database models."""

from sqlalchemy.orm import DeclarativeBase


# handles the Base workflow.
class Base(DeclarativeBase):
    """Base class inherited by all SQLAlchemy models."""
