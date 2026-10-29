"""enforce clinic travel buffer

Revision ID: 3b731aa5093a
Revises: aeffc7436097
Create Date: 2026-10-29 08:42:21.462158

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b731aa5093a"
down_revision: str | Sequence[str] | None = "aeffc7436097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enforce a 60-minute buffer between different clinics."""

    op.execute(
        """
        CREATE FUNCTION check_clinic_travel_buffer()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            -- Inactive shifts do not require conflict checking.
            IF NOT NEW.is_active THEN
                RETURN NEW;
            END IF;

            -- Serialize schedule writes for the same optometrist.
            -- This prevents concurrent inserts from bypassing the check.
            PERFORM 1
            FROM optometrists
            WHERE id = NEW.optometrist_id
            FOR UPDATE;

            IF EXISTS (
                SELECT 1
                FROM working_schedules AS existing
                WHERE existing.optometrist_id = NEW.optometrist_id
                  AND existing.day_of_week = NEW.day_of_week
                  AND existing.clinic_id <> NEW.clinic_id
                  AND existing.is_active = TRUE
                  AND existing.id IS DISTINCT FROM NEW.id
                  AND NEW.start_time < (
                      existing.end_time + INTERVAL '60 minutes'
                  )
                  AND existing.start_time < (
                      NEW.end_time + INTERVAL '60 minutes'
                  )
            ) THEN
                RAISE EXCEPTION
                    'At least 60 minutes required between different clinics'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_check_clinic_travel_buffer
        BEFORE INSERT OR UPDATE
        ON working_schedules
        FOR EACH ROW
        EXECUTE FUNCTION check_clinic_travel_buffer();
        """
    )


def downgrade() -> None:
    """Remove the clinic travel-buffer trigger and function."""

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_check_clinic_travel_buffer
        ON working_schedules;
        """
    )

    op.execute(
        """
        DROP FUNCTION IF EXISTS check_clinic_travel_buffer();
        """
    )
