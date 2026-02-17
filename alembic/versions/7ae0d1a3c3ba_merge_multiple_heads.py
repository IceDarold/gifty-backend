"""merge multiple heads

Revision ID: 7ae0d1a3c3ba
Revises: 48521be6e237, b82385293656
Create Date: 2026-02-13 21:10:31.255506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ae0d1a3c3ba'
down_revision: Union[str, None] = ('48521be6e237', 'b82385293656')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
