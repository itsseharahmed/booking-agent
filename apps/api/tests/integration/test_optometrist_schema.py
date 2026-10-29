"""Integration tests for optometrist and schedule database tables."""

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def test_optometrists_table_exists(test_engine: Engine) -> None:
    """The database should contain an optometrists table."""
    inspector = inspect(test_engine)

    assert "optometrists" in inspector.get_table_names()


def test_optometrist_clinics_table_exists(test_engine: Engine) -> None:
    """The database should contain the clinic association table."""
    inspector = inspect(test_engine)

    assert "optometrist_clinics" in inspector.get_table_names()


def test_working_schedules_table_exists(test_engine: Engine) -> None:
    """The database should contain a working schedules table."""
    inspector = inspect(test_engine)

    assert "working_schedules" in inspector.get_table_names()
