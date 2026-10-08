"""Add trip share/invite links and invited trip members (applies after 009_merge_legacy_road_addr)."""

from alembic import op
import sqlalchemy as sa


revision = "009_trip_share_links"
down_revision = "009_merge_legacy_road_addr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trip_share_links",
        sa.Column("trip_share_link_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trip_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("link_type", sa.Enum("VIEW", "INVITE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.trip_id"], name="fk_trip_share_links_trip", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], name="fk_trip_share_links_user", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trip_share_link_id"),
        sa.UniqueConstraint("token_hash", name="uq_trip_share_links_token_hash"),
        mysql_charset="utf8mb4", mysql_engine="InnoDB",
    )
    op.add_column(
        "trip_companions",
        sa.Column("member_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_trip_companions_member_user",
        "trip_companions", "users",
        ["member_user_id"], ["user_id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_trip_companions_trip_member",
        "trip_companions",
        ["trip_id", "member_user_id"],
    )


def downgrade():
    op.drop_constraint("uq_trip_companions_trip_member", "trip_companions", type_="unique")
    op.drop_constraint("fk_trip_companions_member_user", "trip_companions", type_="foreignkey")
    op.drop_column("trip_companions", "member_user_id")
    op.drop_table("trip_share_links")
