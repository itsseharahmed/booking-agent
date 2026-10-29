"""add appointment services and clinic pricing

Revision ID: 403ca2fb15a7
Revises: d2cb076cca0f
Create Date: 2026-10-29 13:14:08.946365

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "403ca2fb15a7"
down_revision: str | Sequence[str] | None = "d2cb076cca0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "appointment_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column(
        "clinics",
        sa.Column(
            "appointment_price",
            sa.Numeric(precision=10, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_clinics_nonnegative_appointment_price",
        "clinics",
        "appointment_price >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_clinics_nonnegative_appointment_price",
        "clinics",
        type_="check",
    )

    op.drop_column("clinics", "appointment_price")

    op.drop_table("appointment_services")
