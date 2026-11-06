"""Tests for clinic knowledge retrieval."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from optometry.agent.clinic_knowledge import fetch_clinic_knowledge


def make_clinic() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )


def test_returns_clinic_with_knowledge() -> None:
    db = MagicMock()
    knowledge = SimpleNamespace(
        insurance_info="Sun Life accepted",
        parking_info="Free parking",
        accessibility_info="Wheelchair accessible",
        appointment_policy="24-hour cancellation notice",
        additional_info="Open on Saturdays",
    )

    db.execute.return_value.one_or_none.return_value = (
        make_clinic(),
        knowledge,
    )

    result = fetch_clinic_knowledge(db, clinic_id=1)

    assert result is not None
    assert result["name"] == "Test Clinic"
    assert result["insurance_info"] == "Sun Life accepted"
    assert result["parking_info"] == "Free parking"
    assert result["address"]["city"] == "Toronto"


def test_returns_clinic_without_knowledge() -> None:
    db = MagicMock()

    db.execute.return_value.one_or_none.return_value = (
        make_clinic(),
        None,
    )

    result = fetch_clinic_knowledge(db, clinic_id=1)

    assert result is not None
    assert result["name"] == "Test Clinic"
    assert result["insurance_info"] is None
    assert result["appointment_policy"] is None


def test_returns_none_for_missing_or_inactive_clinic() -> None:
    db = MagicMock()
    db.execute.return_value.one_or_none.return_value = None

    assert fetch_clinic_knowledge(db, clinic_id=999) is None


def test_rejects_invalid_clinic_id() -> None:
    db = MagicMock()

    assert fetch_clinic_knowledge(db, clinic_id=0) is None
    assert fetch_clinic_knowledge(db, clinic_id=-1) is None

    db.execute.assert_not_called()
