"""merge heads

Revision ID: a063630851f9
Revises: 1b2c3d4e5f67, 8d5f0c2a9e11
Create Date: 2026-03-04 17:10:50.298917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a063630851f9'
down_revision: Union[str, None] = ('1b2c3d4e5f67', '8d5f0c2a9e11')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
