"""merge remote a063 head with local head

Revision ID: 1ea3169488c4
Revises: a063630851f9, 941376732bf6
Create Date: 2026-03-05 12:25:39.342095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ea3169488c4'
down_revision: Union[str, None] = ('a063630851f9', '941376732bf6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
