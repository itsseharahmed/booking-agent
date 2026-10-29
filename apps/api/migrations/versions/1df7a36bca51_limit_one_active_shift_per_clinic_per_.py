"""limit one active shift per clinic per day

Revision ID: 1df7a36bca51
Revises: 3b731aa5093a
Create Date: 2026-10-29 08:47:07.673572

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1df7a36bca51"
down_revision: str | Sequence[str] | None = "3b731aa5093a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow only one active shift per clinic per weekday."""

    op.create_index(
        "uq_working_schedules_active_clinic_day",
        "working_schedules",
        ["optometrist_id", "clinic_id", "day_of_week"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    """Remove the one-active-shift restriction."""

    op.drop_index(
        "uq_working_schedules_active_clinic_day",
        table_name="working_schedules",
    )
