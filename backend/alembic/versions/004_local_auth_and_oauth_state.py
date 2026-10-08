"""add local authentication and oauth login state

Revision ID: 004_local_auth_and_oauth_state
Revises: 003_setup_preferences
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004_local_auth_and_oauth_state'
down_revision: Union[str, Sequence[str], None] = '003_setup_preferences'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.alter_column('user_auths', 'provider',
        existing_type=sa.Enum('KAKAO', 'NAVER'),
        type_=sa.Enum('LOCAL', 'KAKAO', 'NAVER'),
        existing_nullable=False,
    )
    op.create_table(
        'oauth_login_states',
        sa.Column('oauth_login_state_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.Enum('NAVER'), nullable=False),
        sa.Column('state_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('oauth_login_state_id'),
        sa.UniqueConstraint('state_hash', name='uq_oauth_login_states_hash'),
        mysql_charset='utf8mb4', mysql_engine='InnoDB',
    )


def downgrade() -> None:
    op.drop_table('oauth_login_states')
    op.alter_column('user_auths', 'provider',
        existing_type=sa.Enum('LOCAL', 'KAKAO', 'NAVER'),
        type_=sa.Enum('KAKAO', 'NAVER'),
        existing_nullable=False,
    )
    op.drop_column('users', 'password_hash')
