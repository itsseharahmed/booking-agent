"""Safety checks used by PostgreSQL integration tests."""


def validate_test_database_name(database_name: str) -> None:
    """Reject databases other than the dedicated test database."""

    if database_name != "optometry_booking_test":
        raise ValueError(
            "Unsafe test database configuration: "
            f"connected to '{database_name}' instead of "
            "'optometry_booking_test'."
        )
