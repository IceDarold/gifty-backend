"""merge parsing and frontend control-plane heads

Revision ID: 9b6dcf704bbf
Revises: 9f2a7c1d4b8e, a4b1c2d3e4f5
Create Date: 2026-02-23 19:39:24.068829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b6dcf704bbf'
down_revision: Union[str, None] = ('9f2a7c1d4b8e', 'a4b1c2d3e4f5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
