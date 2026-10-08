"""Persist the existing setup-screen travel style and senior-mode selections."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_setup_preferences"
down_revision: Union[str, Sequence[str], None] = "002_seed_interest_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column(
            "travel_style",
            sa.Enum("SLOW", "STANDARD", "FOOD_FOCUSED"),
            nullable=True,
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column("senior_mode", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
    )
    interest_codes = sa.table(
        "interest_codes",
        sa.column("interest_code", sa.String),
        sa.column("label_ko", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        interest_codes,
        [
            {"interest_code": "CITY", "label_ko": "도시", "sort_order": 9},
            {"interest_code": "REST", "label_ko": "휴식", "sort_order": 10},
            {"interest_code": "SEA", "label_ko": "바다", "sort_order": 11},
        ],
    )


def downgrade() -> None:
    raise RuntimeError("Setup preference rollback is disabled; use a reviewed recovery plan")
