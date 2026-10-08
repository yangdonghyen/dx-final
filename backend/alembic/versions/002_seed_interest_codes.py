"""Seed the documented interest-code master data without changing schema."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_seed_interest_codes"
down_revision: Union[str, Sequence[str], None] = "001_initial_schema"
branch_labels = None
depends_on = None

def upgrade() -> None:
    interest_codes = sa.table("interest_codes", sa.column("interest_code", sa.String), sa.column("label_ko", sa.String), sa.column("sort_order", sa.Integer))
    op.bulk_insert(interest_codes, [
        {"interest_code": "FOOD", "label_ko": "\ub9db\uc9d1", "sort_order": 1},
        {"interest_code": "CAFE", "label_ko": "\uce74\ud398", "sort_order": 2},
        {"interest_code": "NATURE", "label_ko": "\uc790\uc5f0", "sort_order": 3},
        {"interest_code": "CULTURE", "label_ko": "\ubb38\ud654", "sort_order": 4},
        {"interest_code": "HISTORY", "label_ko": "\uc5ed\uc0ac", "sort_order": 5},
        {"interest_code": "SHOPPING", "label_ko": "\uc1fc\ud551", "sort_order": 6},
        {"interest_code": "EXHIBITION", "label_ko": "\uc804\uc2dc", "sort_order": 7},
        {"interest_code": "ACTIVITY", "label_ko": "\uccb4\ud5d8", "sort_order": 8},
    ])

def downgrade() -> None:
    raise RuntimeError("Interest-code seed rollback is disabled; use a reviewed recovery plan")
