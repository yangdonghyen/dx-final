"""Create saved YouTube discoveries.

Revision ID: 007_youtube_saved_discoveries
Revises: 006_trip_preference_travel_style
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_youtube_saved_discoveries"
down_revision: Union[str, Sequence[str], None] = (
    "006_trip_preference_travel_style"
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "youtube_saved_discoveries",
        sa.Column(
            "saved_discovery_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "position_sec",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "page_url",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "channel_title",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "thumbnail_url",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_youtube_saved_discoveries_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "video_id",
            "position_sec",
            name="uq_youtube_saved_discoveries_user_video_position",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_index(
        "ix_youtube_saved_discoveries_user_id",
        "youtube_saved_discoveries",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_youtube_saved_discoveries_user_id",
        table_name="youtube_saved_discoveries",
    )
    op.drop_table("youtube_saved_discoveries")
