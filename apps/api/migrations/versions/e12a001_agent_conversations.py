"""Add persistent agent conversations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e12a001"
down_revision: str | Sequence[str] | None = "c63261bf8999"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("patient_id", "id"),
    )


def downgrade() -> None:
    op.drop_table("agent_conversations")
