"""Add destination fields to saved YouTube discoveries."""

from alembic import op
import sqlalchemy as sa


revision = "008_youtube_destination_fields"
down_revision = "007_youtube_saved_discoveries"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "youtube_saved_discoveries",
        sa.Column("destination_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "youtube_saved_discoveries",
        sa.Column(
            "representative_image_url",
            sa.String(length=1000),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "youtube_saved_discoveries",
        "representative_image_url",
    )
    op.drop_column(
        "youtube_saved_discoveries",
        "destination_name",
    )
