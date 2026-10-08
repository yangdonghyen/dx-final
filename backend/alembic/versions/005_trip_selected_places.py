"""persist user-selected anchor places for each trip

Revision ID: 005_trip_selected_places
Revises: 004_local_auth_and_oauth_state
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '005_trip_selected_places'
down_revision: Union[str, Sequence[str], None] = '004_local_auth_and_oauth_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'trip_selected_places',
        sa.Column('trip_selected_place_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trip_id', sa.BigInteger(), nullable=False),
        sa.Column('place_id', sa.BigInteger(), nullable=False),
        sa.Column('selected_order', mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.trip_id'], name='fk_trip_selected_places_trip', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['place_id'], ['places.place_id'], name='fk_trip_selected_places_place', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('trip_selected_place_id'),
        sa.UniqueConstraint('trip_id', 'place_id', name='uq_trip_selected_places_trip_place'),
        sa.UniqueConstraint('trip_id', 'selected_order', name='uq_trip_selected_places_trip_order'),
        mysql_charset='utf8mb4', mysql_engine='InnoDB',
    )


def downgrade() -> None:
    op.drop_table('trip_selected_places')
