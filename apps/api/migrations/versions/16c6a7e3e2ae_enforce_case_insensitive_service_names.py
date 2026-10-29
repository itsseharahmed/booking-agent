"""enforce case insensitive service names

Revision ID: 16c6a7e3e2ae
Revises: 403ca2fb15a7
Create Date: 2026-10-29 13:34:12.350248

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16c6a7e3e2ae"
down_revision: str | Sequence[str] | None = "403ca2fb15a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_appointment_services_name_lower
        ON appointment_services (lower(name))
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_appointment_services_name_lower",
        table_name="appointment_services",
    )
