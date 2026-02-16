"""merge heads

Revision ID: a385296418a2
Revises: 48521be6e237, b82385293656
Create Date: 2026-02-16 10:58:19.690287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a385296418a2'
down_revision: Union[str, None] = ('48521be6e237', 'b82385293656')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
