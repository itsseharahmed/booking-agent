"""Integration tests for recurring optometrist working schedules."""

from datetime import time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from optometry.db.models.clinic import Clinic
from optometry.db.models.optometrist import Optometrist
from optometry.db.models.optometrist_clinic import OptometristClinic
from optometry.db.models.working_schedule import WorkingSchedule


@pytest.fixture
def assigned_clinic(test_session: Session) -> tuple[int, int]:
    """Create an optometrist assigned to a clinic."""

    optometrist = Optometrist(
        first_name="Alex",
        last_name="Morgan",
    )

    clinic = Clinic(
        name="Schedule Test Clinic",
        address_line1="123 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add_all([optometrist, clinic])
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist.id,
            clinic_id=clinic.id,
        )
    )
    test_session.flush()

    return optometrist.id, clinic.id


def test_create_valid_schedule(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """A valid recurring shift can be saved."""

    optometrist_id, clinic_id = assigned_clinic

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )

    test_session.add(schedule)
    test_session.flush()

    assert schedule.id is not None
    assert schedule.is_active is True


def test_reject_invalid_weekday(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Weekdays outside 0–6 must be rejected."""

    optometrist_id, clinic_id = assigned_clinic

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=7,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )

    test_session.add(schedule)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_reject_invalid_time_range(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """A shift cannot end before it starts."""

    optometrist_id, clinic_id = assigned_clinic

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(17, 0),
        end_time=time(9, 0),
    )

    test_session.add(schedule)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_reject_schedule_at_unassigned_clinic(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Schedules must reference an existing clinic assignment."""

    optometrist_id, _ = assigned_clinic

    other_clinic = Clinic(
        name="Unassigned Clinic",
        address_line1="456 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(other_clinic)
    test_session.flush()

    schedule = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=other_clinic.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )

    test_session.add(schedule)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_reject_overlapping_schedules(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """An optometrist cannot have overlapping active shifts."""

    optometrist_id, clinic_id = assigned_clinic

    morning_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )

    overlapping_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(12, 0),
        end_time=time(17, 0),
    )

    test_session.add(morning_shift)
    test_session.flush()

    test_session.add(overlapping_shift)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_reject_insufficient_travel_time(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Switching clinics requires at least 60 minutes between shifts."""

    optometrist_id, first_clinic_id = assigned_clinic

    second_clinic = Clinic(
        name="Second Schedule Test Clinic",
        address_line1="456 Main Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2T6",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(second_clinic)
    test_session.flush()

    # Assign the same optometrist to the second clinic.
    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist_id,
            clinic_id=second_clinic.id,
        )
    )
    test_session.flush()

    first_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=first_clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )

    second_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=second_clinic.id,
        day_of_week=0,
        start_time=time(13, 30),
        end_time=time(17, 0),
    )

    test_session.add(first_shift)
    test_session.flush()

    test_session.add(second_shift)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_allow_exactly_60_minutes_between_clinics(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Exactly 60 minutes between different clinics is allowed."""

    optometrist_id, first_clinic_id = assigned_clinic

    second_clinic = Clinic(
        name="Travel Buffer Test Clinic",
        address_line1="789 Queen Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 2B4",
        country="CA",
        timezone="America/Toronto",
    )
    test_session.add(second_clinic)
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist_id,
            clinic_id=second_clinic.id,
        )
    )
    test_session.flush()

    first_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=first_clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )

    second_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=second_clinic.id,
        day_of_week=0,
        start_time=time(14, 0),
        end_time=time(17, 0),
    )

    test_session.add_all([first_shift, second_shift])
    test_session.flush()

    assert first_shift.id is not None
    assert second_shift.id is not None


def test_reject_multiple_active_shifts_at_same_clinic(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Only one active shift per clinic per weekday is allowed."""

    optometrist_id, clinic_id = assigned_clinic

    morning_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )

    afternoon_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(13, 0),
        end_time=time(17, 0),
    )

    test_session.add(morning_shift)
    test_session.flush()

    test_session.add(afternoon_shift)

    with pytest.raises(IntegrityError):
        test_session.flush()


def test_inactive_shift_does_not_block_replacement(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """An inactive shift can coexist with an active replacement."""

    optometrist_id, clinic_id = assigned_clinic

    old_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
        is_active=False,
    )

    replacement_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=clinic_id,
        day_of_week=0,
        start_time=time(10, 0),
        end_time=time(17, 0),
        is_active=True,
    )

    test_session.add_all([old_shift, replacement_shift])
    test_session.flush()

    assert old_shift.id is not None
    assert replacement_shift.id is not None
    assert old_shift.is_active is False
    assert replacement_shift.is_active is True


def test_reject_schedule_update_with_insufficient_travel_time(
    test_session: Session,
    assigned_clinic: tuple[int, int],
) -> None:
    """Updating a shift must preserve the 60-minute travel buffer."""

    optometrist_id, first_clinic_id = assigned_clinic

    second_clinic = Clinic(
        name="Schedule Update Test Clinic",
        address_line1="456 King Street",
        city="Toronto",
        province="Ontario",
        postal_code="M5V 1L7",
        country="CA",
        timezone="America/Toronto",
    )

    test_session.add(second_clinic)
    test_session.flush()

    test_session.add(
        OptometristClinic(
            optometrist_id=optometrist_id,
            clinic_id=second_clinic.id,
        )
    )
    test_session.flush()

    first_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=first_clinic_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )

    second_shift = WorkingSchedule(
        optometrist_id=optometrist_id,
        clinic_id=second_clinic.id,
        day_of_week=0,
        start_time=time(14, 0),
        end_time=time(17, 0),
    )

    test_session.add_all([first_shift, second_shift])
    test_session.flush()

    # Move the second shift earlier, leaving only 30 minutes.
    second_shift.start_time = time(13, 30)

    with pytest.raises(IntegrityError):
        test_session.flush()
