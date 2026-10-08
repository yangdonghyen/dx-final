"""Add explicit WALK as a Trip primary transport mode.

This migration is intentionally not executed by this change. Existing OTHER
and MIXED values are retained exactly as stored.
"""

from alembic import op
import sqlalchemy as sa


revision = "011_trip_transport_mode_walk"
down_revision = "010_plan_regeneration_previews"
branch_labels = None
depends_on = None


_OLD_ENUM = sa.Enum("PUBLIC_TRANSIT", "CAR", "MIXED", "OTHER")
_NEW_ENUM = sa.Enum("PUBLIC_TRANSIT", "CAR", "WALK", "MIXED", "OTHER")


def upgrade() -> None:
    op.alter_column(
        "trips",
        "transport_mode",
        existing_type=_OLD_ENUM,
        type_=_NEW_ENUM,
        existing_nullable=True,
    )


def downgrade() -> None:
    # Do not silently reclassify explicit WALK trips as OTHER during rollback.
    count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM trips WHERE transport_mode = 'WALK'")
    ).scalar_one()
    if count:
        raise RuntimeError("Cannot downgrade while trips.transport_mode contains WALK")
    op.alter_column(
        "trips",
        "transport_mode",
        existing_type=_NEW_ENUM,
        type_=_OLD_ENUM,
        existing_nullable=True,
    )
