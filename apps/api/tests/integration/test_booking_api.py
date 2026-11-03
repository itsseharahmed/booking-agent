"""Booking API integration tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from optometry.api.appointments import get_redis_client as get_appointments_redis
from optometry.api.appointments import router as appointments_router
from optometry.api.availability import get_redis_client as get_availability_redis
from optometry.api.availability import router as availability_router
from optometry.core.security import create_access_token, hash_password
from optometry.db.models.appointment import Appointment
from optometry.db.models.appointment_service import AppointmentService
from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.patient import Patient
from optometry.db.models.working_schedule import WorkingSchedule
from optometry.db.session import get_db


# creates the shared test fixture.
@pytest.fixture
# builds the test client used by the test.
def client(test_session, test_redis, monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-only-secret-not-for-production",
    )

    patient = Patient(
        first_name="Booking",
        last_name="Patient",
        email="booking-owner@example.com",
        password_hash=hash_password("secure-test-password-123"),
    )
    test_session.add(patient)
    test_session.flush()

    token = create_access_token(
        patient_id=patient.id,
        secret_key="test-only-secret-not-for-production",
    )

    # creates the api application.
    app = FastAPI()
    app.include_router(appointments_router)
    app.include_router(availability_router)

    # overrides a dependency during the test.
    def override_db():
        yield test_session

    app.dependency_overrides[get_db] = override_db

    # use the isolated redis database for booking tests
    app.dependency_overrides[get_appointments_redis] = lambda: test_redis
    app.dependency_overrides[get_availability_redis] = lambda: test_redis

    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


# creates the shared test fixture.
@pytest.fixture
# handles the booking data workflow.
def booking_data(test_session):
    clinic = Clinic(
        name="Booking API Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
        appointment_price=Decimal("95.00"),
    )
    optometrist = Optometrist(
        first_name="API",
        last_name="Booking",
    )
    service = AppointmentService(
        name="Booking API Eye Exam",
    )

    test_session.add_all([clinic, optometrist, service])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    # find a future Monday so day_of_week=0 is predictable.
    target = datetime.now(UTC).date() + timedelta(days=21)
    target += timedelta(days=(0 - target.weekday()) % 7)

    test_session.add(
        WorkingSchedule(
            clinic_id=clinic.id,
            optometrist_id=optometrist.id,
            day_of_week=0,
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("10:00", "%H:%M").time(),
            is_active=True,
        )
    )
    test_session.flush()

    return {
        "clinic_id": clinic.id,
        "optometrist_id": optometrist.id,
        "service_id": service.id,
        "appointment_date": target.isoformat(),
    }


# handles the availability params workflow.
def availability_params(data):
    return {
        "clinic_id": data["clinic_id"],
        "optometrist_id": data["optometrist_id"],
        "service_id": data["service_id"],
        "appointment_date": data["appointment_date"],
    }


# handles the first available slot workflow.
def first_available_slot(client, data):
    response = client.get(
        "/availability",
        params=availability_params(data),
    )
    assert response.status_code == 200
    slots = response.json()["slots"]
    assert slots
    return slots[0]


# handles the booking payload workflow.
def booking_payload(data, slot):
    return {
        "clinic_id": data["clinic_id"],
        "optometrist_id": data["optometrist_id"],
        "service_id": data["service_id"],
        "start_at": slot["start"],
    }


# checks that create booking works as expected.
def test_create_booking(client, test_session, booking_data):
    slot = first_available_slot(client, booking_data)

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 201

    result = response.json()

    # verify booking response
    assert result["status"] == "booked"
    assert Decimal(result["appointment_price"]) == Decimal("95.00")
    assert result["start_at"] is not None
    assert result["end_at"] is not None

    # verify authenticated patient ownership
    appointment = test_session.get(
        Appointment,
        result["id"],
    )

    assert appointment is not None
    assert appointment.patient_id is not None

    owner = test_session.get(Patient, appointment.patient_id)

    assert owner is not None
    assert owner.email == "booking-owner@example.com"


# checks that booking removes slot from availability works as expected.
def test_booking_removes_slot_from_availability(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    response = client.get(
        "/availability",
        params=availability_params(booking_data),
    )
    assert response.status_code == 200

    starts = [item["start"] for item in response.json()["slots"]]
    assert slot["start"] not in starts


# checks that duplicate booking rejected works as expected.
def test_duplicate_booking_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    second = client.post("/appointments", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


# checks that cancel booking restores slot works as expected.
def test_cancel_booking_restores_slot(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]

    cancelled = client.post(f"/appointments/{appointment_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None

    response = client.get(
        "/availability",
        params=availability_params(booking_data),
    )

    starts = [item["start"] for item in response.json()["slots"]]
    assert slot["start"] in starts


# checks that cancel twice rejected works as expected.
def test_cancel_twice_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    appointment_id = created.json()["id"]

    first = client.post(f"/appointments/{appointment_id}/cancel")
    second = client.post(f"/appointments/{appointment_id}/cancel")

    assert first.status_code == 200
    assert second.status_code == 409


# checks that booking invalid slot rejected works as expected.
def test_booking_invalid_slot_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    invalid_start = datetime.fromisoformat(slot["start"]) + timedelta(minutes=5)

    payload = booking_payload(booking_data, slot)
    payload["start_at"] = invalid_start.isoformat()

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


# checks that get booking works as expected.
def test_get_booking(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    appointment_id = created.json()["id"]

    response = client.get(f"/appointments/{appointment_id}")

    assert response.status_code == 200
    assert response.json()["id"] == appointment_id


# checks that list bookings works as expected.
def test_list_bookings(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    response = client.get(
        "/appointments",
        params={"clinic_id": booking_data["clinic_id"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


# checks that missing booking returns 404 works as expected.
def test_missing_booking_returns_404(client):
    response = client.get("/appointments/99999999")
    assert response.status_code == 404


# checks that naive datetime rejected works as expected.
def test_naive_datetime_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    payload["start_at"] = (
        datetime.fromisoformat(slot["start"]).replace(tzinfo=None).isoformat()
    )

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


# checks that booking price is snapshot works as expected.
def test_booking_price_is_snapshot(client, test_session, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]
    original_price = Decimal(created.json()["appointment_price"])

    clinic = test_session.get(Clinic, booking_data["clinic_id"])
    assert clinic is not None

    clinic.appointment_price = Decimal("150.00")
    test_session.flush()

    response = client.get(f"/appointments/{appointment_id}")

    assert response.status_code == 200
    assert Decimal(response.json()["appointment_price"]) == original_price


# checks that cancelled booking stays in history works as expected.
def test_cancelled_booking_stays_in_history(client, booking_data):
    slot = first_available_slot(client, booking_data)

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]

    cancelled = client.post(f"/appointments/{appointment_id}/cancel")
    assert cancelled.status_code == 200

    response = client.get(
        "/appointments",
        params={
            "clinic_id": booking_data["clinic_id"],
            "status": "cancelled",
        },
    )

    assert response.status_code == 200
    assert any(item["id"] == appointment_id for item in response.json())


# checks that rebooking after cancellation works as expected.
def test_rebooking_after_cancellation(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    assert first.status_code == 201

    cancelled = client.post(f"/appointments/{first.json()['id']}/cancel")
    assert cancelled.status_code == 200

    replacement = client.post("/appointments", json=payload)

    assert replacement.status_code == 201
    assert replacement.json()["id"] != first.json()["id"]


# checks that occupied slot is conflict not invalid time works as expected.
def test_occupied_slot_is_conflict_not_invalid_time(client, booking_data):
    slot = first_available_slot(client, booking_data)
    payload = booking_payload(booking_data, slot)

    first = client.post("/appointments", json=payload)
    assert first.status_code == 201

    second = client.post("/appointments", json=payload)

    assert second.status_code == 409


# checks that booking outside working hours rejected works as expected.
def test_booking_outside_working_hours_rejected(client, booking_data):
    slot = first_available_slot(client, booking_data)

    outside_start = datetime.fromisoformat(slot["start"]) - timedelta(minutes=20)

    payload = booking_payload(booking_data, slot)
    payload["start_at"] = outside_start.isoformat()

    response = client.post("/appointments", json=payload)

    assert response.status_code == 422


# checks that booking with inactive service rejected works as expected.
def test_booking_with_inactive_service_rejected(client, test_session, booking_data):
    slot = first_available_slot(client, booking_data)

    service = test_session.get(
        AppointmentService,
        booking_data["service_id"],
    )
    assert service is not None

    service.is_active = False
    test_session.flush()

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 422


# checks that cancel missing booking returns 404 works as expected.
def test_cancel_missing_booking_returns_404(client):
    response = client.post("/appointments/99999999/cancel")
    assert response.status_code == 404


# checks that appointment interval is twenty minutes works as expected.
def test_appointment_interval_is_twenty_minutes(client, booking_data):
    slot = first_available_slot(client, booking_data)

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 201

    start = datetime.fromisoformat(response.json()["start_at"])
    end = datetime.fromisoformat(response.json()["end_at"])

    assert end - start == timedelta(minutes=20)


# checks that booking response uses toronto timezone works as expected.
def test_booking_response_uses_toronto_timezone(
    client,
    booking_data,
):
    slot = first_available_slot(client, booking_data)

    response = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert response.status_code == 201

    result = response.json()

    assert result["start_at"] == slot["start"]
    assert result["end_at"] == slot["end"]


# checks that repeated availability requests use redis
def test_availability_uses_real_redis_cache(
    client,
    test_redis,
    booking_data,
    monkeypatch,
):
    import optometry.api.availability as availability_api

    calls = 0
    original = availability_api.get_availability

    def tracked_availability(**kwargs):
        nonlocal calls
        calls += 1
        return original(**kwargs)

    monkeypatch.setattr(
        availability_api,
        "get_availability",
        tracked_availability,
    )

    first = client.get(
        "/availability",
        params=availability_params(booking_data),
    )
    second = client.get(
        "/availability",
        params=availability_params(booking_data),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1
    assert test_redis.dbsize() > 0


# checks that booking invalidates cached availability in redis
def test_booking_invalidates_real_redis_cache(
    client,
    test_redis,
    booking_data,
):
    params = availability_params(booking_data)

    # populate the cache before booking
    before = client.get("/availability", params=params)
    assert before.status_code == 200

    slot = before.json()["slots"][0]

    old_keys = set(test_redis.scan_iter(match="availability:v3:*"))
    assert len(old_keys) == 1

    # book a slot using the real appointment endpoint
    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    # the booking must increment the doctor and date version
    version_key = (
        f"availability:version:doctor:{booking_data['optometrist_id']}:"
        f"date:{booking_data['appointment_date']}"
    )
    assert test_redis.get(version_key) == "1"

    # the next request must use a new cache key
    after = client.get("/availability", params=params)
    assert after.status_code == 200

    starts = [item["start"] for item in after.json()["slots"]]
    assert slot["start"] not in starts

    new_keys = set(test_redis.scan_iter(match="availability:v3:*"))
    assert len(new_keys - old_keys) == 1


# checks that cancellation invalidates cached availability in redis
def test_cancellation_invalidates_real_redis_cache(
    client,
    test_redis,
    booking_data,
):
    params = availability_params(booking_data)

    # load an available slot
    initial = client.get("/availability", params=params)
    assert initial.status_code == 200
    slot = initial.json()["slots"][0]

    # book the slot
    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201
    appointment_id = created.json()["id"]

    # cache availability while the slot is booked
    booked = client.get("/availability", params=params)
    assert booked.status_code == 200
    assert slot["start"] not in [item["start"] for item in booked.json()["slots"]]

    booked_keys = set(test_redis.scan_iter(match="availability:v3:*"))

    version_key = (
        f"availability:version:doctor:{booking_data['optometrist_id']}:"
        f"date:{booking_data['appointment_date']}"
    )
    assert test_redis.get(version_key) == "1"

    # cancel the appointment
    cancelled = client.post(f"/appointments/{appointment_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # cancellation must advance the cache version
    assert test_redis.get(version_key) == "2"

    # the cancelled slot must become available again
    restored = client.get("/availability", params=params)
    assert restored.status_code == 200
    assert slot["start"] in [item["start"] for item in restored.json()["slots"]]

    # a new versioned cache entry must be created
    restored_keys = set(test_redis.scan_iter(match="availability:v3:*"))
    assert len(restored_keys - booked_keys) == 1


# checks that rejected cancellation does not invalidate redis
def test_rejected_cancellation_preserves_cache_version(
    client,
    test_redis,
    booking_data,
):
    params = availability_params(booking_data)

    initial = client.get("/availability", params=params)
    assert initial.status_code == 200
    slot = initial.json()["slots"][0]

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )
    assert created.status_code == 201

    appointment_id = created.json()["id"]

    # cancel the appointment successfully
    first = client.post(f"/appointments/{appointment_id}/cancel")
    assert first.status_code == 200

    version_key = (
        f"availability:version:doctor:{booking_data['optometrist_id']}:"
        f"date:{booking_data['appointment_date']}"
    )

    version_before = test_redis.get(version_key)
    assert version_before == "2"

    # the second cancellation must fail without invalidation
    second = client.post(f"/appointments/{appointment_id}/cancel")
    assert second.status_code == 409

    version_after = test_redis.get(version_key)

    assert version_after == version_before


# checks that redis failure after commit does not undo a booking
def test_booking_survives_redis_invalidation_failure(
    client,
    test_session,
    booking_data,
    monkeypatch,
):
    from redis.exceptions import ConnectionError

    import optometry.api.appointments as appointments_api

    response = client.get(
        "/availability",
        params=availability_params(booking_data),
    )
    assert response.status_code == 200
    slot = response.json()["slots"][0]

    original = appointments_api.invalidate_availability

    # simulate a redis connection error through the actual client
    def failed_invalidation(*, client, optometrist_id, appointment_date):
        with monkeypatch.context() as patch:
            patch.setattr(
                client,
                "incr",
                lambda key: (_ for _ in ()).throw(ConnectionError("Redis unavailable")),
            )
            return original(
                client=client,
                optometrist_id=optometrist_id,
                appointment_date=appointment_date,
            )

    monkeypatch.setattr(
        appointments_api,
        "invalidate_availability",
        failed_invalidation,
    )

    created = client.post(
        "/appointments",
        json=booking_payload(booking_data, slot),
    )

    assert created.status_code == 201

    appointment = test_session.get(
        Appointment,
        created.json()["id"],
    )

    assert appointment is not None
    assert appointment.status == "booked"


# checks stale availability recovers after cache expiration
def test_availability_recovers_after_failed_invalidation(
    client,
    test_redis,
    booking_data,
    monkeypatch,
):
    from redis.exceptions import ConnectionError

    params = availability_params(booking_data)

    # populate the real redis cache
    initial = client.get("/availability", params=params)
    assert initial.status_code == 200
    slot = initial.json()["slots"][0]

    keys = list(test_redis.scan_iter(match="availability:v3:*"))
    assert len(keys) == 1
    cached_key = keys[0]

    # simulate redis failure only during booking invalidation
    def failed_increment(key):
        raise ConnectionError("Redis unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(test_redis, "incr", failed_increment)

        created = client.post(
            "/appointments",
            json=booking_payload(booking_data, slot),
        )

    assert created.status_code == 201

    # the stale entry remains because invalidation failed
    assert test_redis.exists(cached_key) == 1

    stale = client.get("/availability", params=params)
    assert stale.status_code == 200
    assert slot["start"] in [item["start"] for item in stale.json()["slots"]]

    # simulate expiration without waiting 30 seconds
    test_redis.delete(cached_key)

    recovered = client.get("/availability", params=params)
    assert recovered.status_code == 200
    assert slot["start"] not in [item["start"] for item in recovered.json()["slots"]]


# checks that invalidation during calculation prevents stale caching
def test_invalidation_during_availability_calculation(
    client,
    test_redis,
    booking_data,
    monkeypatch,
):
    import optometry.api.availability as availability_api

    params = availability_params(booking_data)
    original = availability_api.get_availability

    version_key = (
        f"availability:version:doctor:{booking_data['optometrist_id']}:"
        f"date:{booking_data['appointment_date']}"
    )

    # invalidate while the availability service runs
    def invalidate_during_calculation(**kwargs):
        result = original(**kwargs)
        test_redis.incr(version_key)
        return result

    monkeypatch.setattr(
        availability_api,
        "get_availability",
        invalidate_during_calculation,
    )

    response = client.get("/availability", params=params)

    assert response.status_code == 200
    assert test_redis.get(version_key) == "1"

    # the outdated cache version must not be stored
    keys = list(test_redis.scan_iter(match="availability:v3:*"))
    assert keys == []
