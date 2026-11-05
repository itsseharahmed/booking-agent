"""Tests for one-time patient confirmations."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Self

import pytest

from optometry.agent.tools.confirmation import (
    BookingDetails,
    CancellationDetails,
    confirm_request,
    consume_confirmation,
    prepare_confirmation,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lock = Lock()

    def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> bool:
        assert ex > 0

        with self.lock:
            if nx and key in self.values:
                return False

            self.values[key] = value
            return True

    def get(self, key: str) -> str | None:
        with self.lock:
            return self.values.get(key)

    def getdel(self, key: str) -> str | None:
        with self.lock:
            return self.values.pop(key, None)

    def eval(
        self,
        script: str,
        numkeys: int,
        *args: Any,
    ) -> int | str | None:
        with self.lock:
            if "confirmation:approve" in script:
                assert numkeys == 2

                pending_key, approved_key, patient_id, _ttl = args
                raw = self.values.get(pending_key)

                if raw is None:
                    return 0

                record = json.loads(raw)

                if record["patient_id"] != int(patient_id):
                    return 0

                if approved_key in self.values:
                    return 0

                self.values[approved_key] = raw
                del self.values[pending_key]

                return 1

            if "confirmation:consume" in script:
                assert numkeys == 1

                approved_key, patient_id, action = args
                raw = self.values.get(approved_key)

                if raw is None:
                    return None

                record = json.loads(raw)

                if record["patient_id"] != int(patient_id):
                    return None

                if record["action"] != action:
                    return None

                del self.values[approved_key]
                return raw

            raise ValueError("Unknown Redis script")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        pass


# checks booking approval and replay protection
def test_booking_confirmation_is_single_use() -> None:
    client = FakeRedis()

    details = BookingDetails(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=datetime(2026, 11, 10, 15, tzinfo=UTC),
        appointment_price=Decimal("95.00"),
    )

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="book",
        details=details,
    )

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=client,
            patient_id=7,
            token=token,
            action="book",
        )

    assert confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )

    approved = consume_confirmation(
        client=client,
        patient_id=7,
        token=token,
        action="book",
    )

    assert approved == details

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=client,
            patient_id=7,
            token=token,
            action="book",
        )

    assert not confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )


# checks another patient cannot approve the action
def test_confirmation_rejects_wrong_patient() -> None:
    client = FakeRedis()

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert not confirm_request(
        client=client,
        patient_id=8,
        token=token,
    )

    assert confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=client,
            patient_id=8,
            token=token,
            action="cancel",
        )


# checks booking tokens cannot authorize cancellations
def test_confirmation_rejects_wrong_action() -> None:
    client = FakeRedis()

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=client,
            patient_id=7,
            token=token,
            action="book",
        )


# checks cancellation approval contains the exact appointment
def test_cancellation_confirmation() -> None:
    client = FakeRedis()

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )

    approved = consume_confirmation(
        client=client,
        patient_id=7,
        token=token,
        action="cancel",
    )

    assert isinstance(approved, CancellationDetails)
    assert approved.appointment_id == 42


# checks invalid patient identity is rejected
def test_prepare_confirmation_requires_patient() -> None:
    with pytest.raises(ValueError, match="authenticated patient"):
        prepare_confirmation(
            client=FakeRedis(),
            patient_id=0,
            action="cancel",
            details=CancellationDetails(appointment_id=42),
        )


# checks action and details must agree
def test_prepare_confirmation_rejects_wrong_details() -> None:
    with pytest.raises(ValueError, match="do not match"):
        prepare_confirmation(
            client=FakeRedis(),
            patient_id=7,
            action="book",
            details=CancellationDetails(appointment_id=42),
        )


# checks booking times require timezone information
def test_booking_confirmation_rejects_naive_datetime() -> None:
    details = BookingDetails(
        clinic_id=1,
        optometrist_id=2,
        service_id=3,
        start_at=datetime(2026, 11, 10, 15),
        appointment_price=Decimal("95.00"),
    )

    with pytest.raises(ValueError, match="timezone"):
        prepare_confirmation(
            client=FakeRedis(),
            patient_id=7,
            action="book",
            details=details,
        )


# checks concurrent approval cannot promote the same token twice
def test_concurrent_confirmation_approval() -> None:
    client = FakeRedis()

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    def approve() -> bool:
        return confirm_request(
            client=client,
            patient_id=7,
            token=token,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: approve(), range(2)))

    assert results.count(True) == 1
    assert results.count(False) == 1


# checks concurrent requests cannot consume the same approval
def test_concurrent_confirmation_consumption() -> None:
    client = FakeRedis()

    token = prepare_confirmation(
        client=client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=client,
        patient_id=7,
        token=token,
    )

    def consume() -> bool:
        try:
            consume_confirmation(
                client=client,
                patient_id=7,
                token=token,
                action="cancel",
            )
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume(), range(2)))

    assert results.count(True) == 1
    assert results.count(False) == 1
