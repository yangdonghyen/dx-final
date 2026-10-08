"""Add independent pending storage for itinerary-regeneration previews."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "010_plan_regeneration_previews"
down_revision = "009_trip_share_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_regeneration_previews",
        sa.Column("preview_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("base_version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPLIED", "CANCELLED", "EXPIRED"), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("reason", sa.Enum("USER_FATIGUE", "WEATHER_CHANGE"), nullable=False),
        sa.Column("feedback_codes", sa.JSON(), nullable=False),
        sa.Column("current_itinerary_snapshot", sa.JSON(), nullable=False),
        sa.Column("proposed_itinerary", sa.JSON(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["travel_plans.plan_id"], name="fk_plan_regeneration_previews_plan", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_plan_regeneration_previews_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("preview_id"), mysql_charset="utf8mb4", mysql_engine="InnoDB",
    )
    op.create_index("ix_plan_regeneration_previews_plan_status", "plan_regeneration_previews", ["plan_id", "status"])
    op.create_index("ix_plan_regeneration_previews_expires_at", "plan_regeneration_previews", ["expires_at"])


def downgrade() -> None:
    # MySQL may use the composite plan/status index to satisfy the plan FK.
    # Dropping the table removes both the FK and its supporting indexes safely.
    op.drop_table("plan_regeneration_previews")
