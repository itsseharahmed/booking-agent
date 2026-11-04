"""Tests for optometrist and service LangChain tools."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from optometry.agent.tools.optometrists import (
    fetch_active_optometrists,
    list_active_optometrists,
)
from optometry.agent.tools.services import (
    fetch_active_services,
    list_active_services,
)


# checks inactive optometrists are excluded
def test_fetch_active_optometrists() -> None:
    db = MagicMock()

    doctors = [
        SimpleNamespace(
            id=1,
            first_name="Jane",
            last_name="Smith",
            is_active=True,
        ),
        SimpleNamespace(
            id=2,
            first_name="John",
            last_name="Doe",
            is_active=False,
        ),
    ]

    with patch(
        "optometry.agent.tools.optometrists.fetch_optometrists",
        return_value=doctors,
    ) as mock_fetch:
        result = fetch_active_optometrists(db)

    mock_fetch.assert_called_once_with(db=db)

    assert result == [
        {
            "id": 1,
            "first_name": "Jane",
            "last_name": "Smith",
        }
    ]


# checks optometrist tool execution
def test_list_active_optometrists() -> None:
    expected = [{"id": 1, "first_name": "Jane", "last_name": "Smith"}]

    with (
        patch("optometry.agent.tools.optometrists.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.optometrists.fetch_active_optometrists",
            return_value=expected,
        ) as mock_fetch,
    ):
        result = list_active_optometrists.invoke({})

    assert result == expected
    mock_session.assert_called_once_with()
    mock_fetch.assert_called_once_with(mock_session.return_value.__enter__.return_value)


# checks active service filtering
def test_fetch_active_services() -> None:
    db = MagicMock()
    services = [SimpleNamespace(id=3, name="Comprehensive Eye Exam")]

    with patch(
        "optometry.agent.tools.services.fetch_services",
        return_value=services,
    ) as mock_fetch:
        result = fetch_active_services(db)

    mock_fetch.assert_called_once_with(db=db, active_only=True)

    assert result == [
        {
            "id": 3,
            "name": "Comprehensive Eye Exam",
        }
    ]


# checks service tool execution
def test_list_active_services() -> None:
    expected = [{"id": 3, "name": "Comprehensive Eye Exam"}]

    with (
        patch("optometry.agent.tools.services.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.services.fetch_active_services",
            return_value=expected,
        ) as mock_fetch,
    ):
        result = list_active_services.invoke({})

    assert result == expected
    mock_session.assert_called_once_with()
    mock_fetch.assert_called_once_with(mock_session.return_value.__enter__.return_value)
