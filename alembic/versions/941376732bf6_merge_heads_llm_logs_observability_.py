"""merge heads (llm_logs observability + parsing)

Revision ID: 941376732bf6
Revises: 1b2c3d4e5f67, 8d5f0c2a9e11
Create Date: 2026-03-05 12:21:03.654977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '941376732bf6'
down_revision: Union[str, None] = ('1b2c3d4e5f67', '8d5f0c2a9e11')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
