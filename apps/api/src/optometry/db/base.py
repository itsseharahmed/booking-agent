"""Shared declarative base for database models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by all SQLAlchemy models."""
