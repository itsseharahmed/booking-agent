"""Tests for database isolation safeguards."""

import pytest

from tests.database_safety import validate_test_database_name


# checks that accepts test database works as expected.
def test_accepts_test_database() -> None:
    """The dedicated test database must be accepted."""
    validate_test_database_name("optometry_booking_test")


# checks that rejects development database works as expected.
def test_rejects_development_database() -> None:
    """The development database must never be accepted."""
    with pytest.raises(ValueError, match="Unsafe test database"):
        validate_test_database_name("optometry_booking")


# checks that rejects other database works as expected.
def test_rejects_other_database() -> None:
    """An unexpected database name must also be rejected."""
    with pytest.raises(ValueError, match="Unsafe test database"):
        validate_test_database_name("postgres")
