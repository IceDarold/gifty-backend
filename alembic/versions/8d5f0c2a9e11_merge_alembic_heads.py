"""merge alembic heads

Revision ID: 8d5f0c2a9e11
Revises: a4b1c2d3e4f5, b8d0b0b376d9
Create Date: 2026-03-04 05:53:00.043396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d5f0c2a9e11'
down_revision: Union[str, None] = ('a4b1c2d3e4f5', 'b8d0b0b376d9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
