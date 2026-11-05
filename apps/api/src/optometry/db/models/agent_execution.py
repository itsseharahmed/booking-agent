"""Durable records for idempotent agent actions."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from optometry.db.base import Base


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    __table_args__ = (
        CheckConstraint(
            "action IN ('book', 'cancel')",
            name="ck_agent_executions_action",
        ),
        CheckConstraint(
            "status IN ('prepared', 'completed')",
            name="ck_agent_executions_status",
        ),
        CheckConstraint(
            "(status = 'prepared' AND result IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'completed' AND result IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_agent_executions_completion",
        ),
    )

    # sha256 of the confirmation token; never store the raw token
    token_hash: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # server-validated confirmation details
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="prepared",
        server_default="prepared",
    )

    # the original successful API response
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
