import pytest
from pydantic import ValidationError

from optometry.schemas.clinic import ClinicCreate


def test_reject_clinic_with_different_timezone() -> None:
    """Clinics outside the supported timezone must be rejected."""

    with pytest.raises(ValidationError):
        ClinicCreate(
            name="Different Timezone Clinic",
            address_line1="123 Main Street",
            city="Toronto",
            province="Ontario",
            postal_code="M5V 2T6",
            country="CA",
            timezone="America/Vancouver",
        )
