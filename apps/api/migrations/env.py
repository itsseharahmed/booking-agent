"""Alembic environment for the optometry booking database."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from optometry.core.config import get_database_url
from optometry.db.base import Base
from optometry.db.models.clinic import Clinic  # noqa: F401
from optometry.db.models.optometrist import Optometrist  # noqa: F401
from optometry.db.models.optometrist_clinic import OptometristClinic  # noqa: F401
from optometry.db.models.schema_check import SchemaCheck  # noqa: F401
from optometry.db.models.working_schedule import WorkingSchedule  # noqa: F401

# Alembic configuration loaded from alembic.ini.
config = context.config

# Configure logging when a logging configuration exists.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compares this metadata with the database schema.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate migration SQL without connecting to PostgreSQL."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Execute migrations against PostgreSQL."""

    # Use the same connection settings as our application.
    # NullPool prevents Alembic from retaining connections.
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
