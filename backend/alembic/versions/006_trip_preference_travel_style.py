"""Snapshot user travel style on each trip preference.

Revision ID: 006_trip_preference_travel_style
Revises: 005_trip_selected_places
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_trip_preference_travel_style"
down_revision: Union[str, Sequence[str], None] = "005_trip_selected_places"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip_preferences",
        sa.Column("travel_style", sa.Enum("SLOW", "STANDARD", "FOOD_FOCUSED"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trip_preferences", "travel_style")
