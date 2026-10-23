"""Integration tests for Alembic-managed database schema."""

from sqlalchemy import Engine, inspect


def test_schema_check_table_exists(test_engine: Engine) -> None:
    """Verify that the initial migration creates the schema_check table."""
    assert inspect(test_engine).has_table("schema_check")


def test_schema_check_has_expected_columns(test_engine: Engine) -> None:
    """Verify the expected schema after migration."""
    columns = {
        column["name"] for column in inspect(test_engine).get_columns("schema_check")
    }

    assert columns == {"id", "created_at"}
