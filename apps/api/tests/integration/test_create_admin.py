"""Tests for the administrator bootstrap service."""

import pytest
from sqlalchemy.orm import Session

from optometry.admin.create_admin import create_admin
from optometry.core.security import verify_password
from optometry.db.models.admin import Admin


# checks that create admin works as expected.
def test_create_admin(
    test_session: Session,
) -> None:
    admin = create_admin(
        db=test_session,
        email="Admin@Example.com",
        password="SecurePassword123!",
    )

    assert admin.id is not None
    assert admin.email == "admin@example.com"
    assert admin.is_active is True
    assert admin.password_hash != "SecurePassword123!"
    assert verify_password(
        "SecurePassword123!",
        admin.password_hash,
    )


# checks that create admin rejects duplicate email works as expected.
def test_create_admin_rejects_duplicate_email(
    test_session: Session,
) -> None:
    create_admin(
        db=test_session,
        email="admin@example.com",
        password="SecurePassword123!",
    )

    with pytest.raises(ValueError, match="already exists"):
        create_admin(
            db=test_session,
            email="ADMIN@example.com",
            password="AnotherPassword123!",
        )


# checks that create admin rejects short password works as expected.
def test_create_admin_rejects_short_password(
    test_session: Session,
) -> None:
    with pytest.raises(ValueError, match="at least 12"):
        create_admin(
            db=test_session,
            email="admin@example.com",
            password="short",
        )


# checks that create admin rejects invalid email works as expected.
def test_create_admin_rejects_invalid_email(
    test_session: Session,
) -> None:
    with pytest.raises(ValueError, match="Invalid email"):
        create_admin(
            db=test_session,
            email="not-an-email",
            password="SecurePassword123!",
        )


# checks that create admin does not store plaintext password works as expected.
def test_create_admin_does_not_store_plaintext_password(
    test_session: Session,
) -> None:
    admin = create_admin(
        db=test_session,
        email="security@example.com",
        password="SecurePassword123!",
    )

    stored = test_session.get(Admin, admin.id)

    assert stored is not None
    assert stored.password_hash != "SecurePassword123!"
