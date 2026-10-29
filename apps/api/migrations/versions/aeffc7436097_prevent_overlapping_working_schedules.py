"""prevent overlapping working schedules

Revision ID: aeffc7436097
Revises: bc4e7df72a0f
Create Date: 2026-10-29 08:37:38.799323

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aeffc7436097"
down_revision: str | Sequence[str] | None = "bc4e7df72a0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Prevent overlapping active shifts for the same optometrist."""

    # GiST needs btree_gist to compare integer IDs with equality.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # An exclusion constraint prevents intersecting time ranges
    # for the same optometrist on the same weekday.
    op.execute(
        """
        ALTER TABLE working_schedules
        ADD CONSTRAINT ex_working_schedules_no_overlap
        EXCLUDE USING gist (
            optometrist_id WITH =,
            day_of_week WITH =,
            tsrange(
                DATE '2000-01-01' + start_time,
                DATE '2000-01-01' + end_time,
                '[)'
            ) WITH &&
        )
        WHERE (is_active)
        """
    )


def downgrade() -> None:
    """Remove the schedule overlap constraint."""

    op.execute(
        """
        ALTER TABLE working_schedules
        DROP CONSTRAINT ex_working_schedules_no_overlap
        """
    )
