"""merge heads

Revision ID: 7503b6117751
Revises: a9d1c4e5f6b7, d4a1b4e9c2f0
Create Date: 2026-03-13 10:28:25.452205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7503b6117751'
down_revision: Union[str, None] = ('a9d1c4e5f6b7', 'd4a1b4e9c2f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
