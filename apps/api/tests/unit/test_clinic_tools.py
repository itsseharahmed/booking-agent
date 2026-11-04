"""Tests for LangChain clinic tools."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from optometry.agent.tools.clinics import fetch_active_clinics, list_active_clinics


# checks that only active clinics are requested
def test_fetch_active_clinics() -> None:
    db = MagicMock()

    clinic = SimpleNamespace(
        id=1,
        name="Downtown Eye Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 1A1",
    )

    with patch(
        "optometry.agent.tools.clinics.fetch_clinics",
        return_value=[clinic],
    ) as mock_fetch:
        result = fetch_active_clinics(db)

    mock_fetch.assert_called_once_with(db=db, active_only=True)

    assert result == [
        {
            "id": 1,
            "name": "Downtown Eye Clinic",
            "address_line1": "123 Main Street",
            "city": "Toronto",
            "province": "Ontario",
            "postal_code": "M5V 1A1",
        }
    ]


# checks that the langchain tool uses a database session
def test_list_active_clinics() -> None:
    expected = [{"id": 1, "name": "Downtown Eye Clinic"}]

    with (
        patch("optometry.agent.tools.clinics.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.clinics.fetch_active_clinics",
            return_value=expected,
        ) as mock_fetch,
    ):
        result = list_active_clinics.invoke({})

    assert result == expected
    mock_session.assert_called_once_with()
    mock_fetch.assert_called_once_with(mock_session.return_value.__enter__.return_value)
