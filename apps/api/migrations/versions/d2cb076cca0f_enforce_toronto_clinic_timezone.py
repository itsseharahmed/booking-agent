"""enforce Toronto clinic timezone

Revision ID: d2cb076cca0f
Revises: 1df7a36bca51
Create Date: 2026-10-29 09:02:37.514245

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2cb076cca0f"
down_revision: str | Sequence[str] | None = "1df7a36bca51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require all clinics to use America/Toronto."""

    op.create_check_constraint(
        "ck_clinics_toronto_timezone",
        "clinics",
        "timezone = 'America/Toronto'",
    )


def downgrade() -> None:
    """Remove the single-timezone restriction."""

    op.drop_constraint(
        "ck_clinics_toronto_timezone",
        "clinics",
        type_="check",
    )
