"""Tests for optometrist and service LangChain tools."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from optometry.agent.tools.optometrists import (
    fetch_active_optometrists,
    list_active_optometrists,
)
from optometry.agent.tools.services import (
    fetch_active_services,
    list_active_services,
)


# checks clinic-specific optometrist lookup
def test_fetch_active_optometrists() -> None:
    db = MagicMock()

    doctor = SimpleNamespace(
        id=1,
        first_name="Jane",
        last_name="Smith",
    )

    db.scalars.return_value.all.return_value = [doctor]

    result = fetch_active_optometrists(db, clinic_id=3)

    assert result == [
        {
            "id": 1,
            "first_name": "Jane",
            "last_name": "Smith",
        }
    ]

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    sql = str(statement.compile())

    assert "optometrist_clinics" in sql
    assert "clinics" in sql
    assert "is_active" in sql
    assert "clinic_id" in sql or "clinics.id" in sql


# checks tool execution with clinic id
def test_list_active_optometrists() -> None:
    expected = [
        {
            "id": 1,
            "first_name": "Jane",
            "last_name": "Smith",
        }
    ]

    with (
        patch("optometry.agent.tools.optometrists.SessionLocal") as mock_session,
        patch(
            "optometry.agent.tools.optometrists.fetch_active_optometrists",
            return_value=expected,
        ) as mock_fetch,
    ):
        result = list_active_optometrists.invoke({"clinic_id": 3})

    assert result == expected

    mock_session.assert_called_once_with()

    mock_fetch.assert_called_once_with(
        mock_session.return_value.__enter__.return_value,
        3,
    )


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


# checks invalid clinic ids are rejected
def test_fetch_active_optometrists_rejects_invalid_clinic() -> None:
    with pytest.raises(ValueError, match="valid clinic ID"):
        fetch_active_optometrists(MagicMock(), clinic_id=0)


# checks lookup returns empty list when no doctors match
def test_fetch_active_optometrists_no_results() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    result = fetch_active_optometrists(db, clinic_id=3)

    assert result == []
