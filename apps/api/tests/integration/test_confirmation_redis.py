"""Integration tests for atomic Redis confirmations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from redis import Redis

from optometry.agent.tools.confirmation import (
    BookingDetails,
    CancellationDetails,
    confirm_request,
    consume_confirmation,
    prepare_confirmation,
)


@pytest.fixture
def redis_client() -> Redis:
    #use a dedicated test database
    client = Redis(
        host="localhost",
        port=6379,
        db=1,
        decode_responses=True,
        socket_timeout=5,
    )

    client.ping()
    yield client
    client.close()


#checks real Redis executes the approval and consume scripts
def test_redis_confirmation_lifecycle(redis_client: Redis) -> None:
    patient_id = 7
    appointment_id = 42

    token = prepare_confirmation(
        client=redis_client,
        patient_id=patient_id,
        action="cancel",
        details=CancellationDetails(appointment_id=appointment_id),
    )

    assert confirm_request(
        client=redis_client,
        patient_id=patient_id,
        token=token,
    )

    approved = consume_confirmation(
        client=redis_client,
        patient_id=patient_id,
        token=token,
        action="cancel",
    )

    assert isinstance(approved, CancellationDetails)
    assert approved.appointment_id == appointment_id

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=redis_client,
            patient_id=patient_id,
            token=token,
            action="cancel",
        )


#checks only one concurrent request can approve a token
def test_redis_concurrent_approval(redis_client: Redis) -> None:
    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    def approve(_: int) -> bool:
        return confirm_request(
            client=redis_client,
            patient_id=7,
            token=token,
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(approve, range(10)))

    assert results.count(True) == 1
    assert results.count(False) == 9


#checks only one concurrent request can consume approval
def test_redis_concurrent_consumption(redis_client: Redis) -> None:
    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    def consume(_: int) -> bool:
        try:
            consume_confirmation(
                client=redis_client,
                patient_id=7,
                token=token,
                action="cancel",
            )
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(consume, range(10)))

    assert results.count(True) == 1
    assert results.count(False) == 9


#checks Redis rejects wrong-patient confirmation
def test_redis_rejects_wrong_patient(redis_client: Redis) -> None:
    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert not confirm_request(
        client=redis_client,
        patient_id=8,
        token=token,
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=redis_client,
            patient_id=8,
            token=token,
            action="cancel",
        )

    approved = consume_confirmation(
        client=redis_client,
        patient_id=7,
        token=token,
        action="cancel",
    )

    assert isinstance(approved, CancellationDetails)


#checks Redis rejects using cancellation approval for booking
def test_redis_rejects_wrong_action(redis_client: Redis) -> None:
    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="cancel",
        details=CancellationDetails(appointment_id=42),
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    with pytest.raises(PermissionError):
        consume_confirmation(
            client=redis_client,
            patient_id=7,
            token=token,
            action="book",
        )

    approved = consume_confirmation(
        client=redis_client,
        patient_id=7,
        token=token,
        action="cancel",
    )

    assert isinstance(approved, CancellationDetails)


#checks booking details survive serialization
def test_redis_booking_details(redis_client: Redis) -> None:
    start = datetime.now(UTC) + timedelta(days=7)

    token = prepare_confirmation(
        client=redis_client,
        patient_id=7,
        action="book",
        details=BookingDetails(
            clinic_id=1,
            optometrist_id=2,
            service_id=3,
            start_at=start,
        ),
    )

    assert confirm_request(
        client=redis_client,
        patient_id=7,
        token=token,
    )

    approved = consume_confirmation(
        client=redis_client,
        patient_id=7,
        token=token,
        action="book",
    )

    assert isinstance(approved, BookingDetails)
    assert approved.clinic_id == 1
    assert approved.optometrist_id == 2
    assert approved.service_id == 3
    assert approved.start_at == start