"""add language to telegram subscriber

Revision ID: d9e0f1a2b3c4
Revises: c8b2e3f4d5a6
Create Date: 2026-02-08 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, None] = 'c8b2e3f4d5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('telegram_subscribers', sa.Column('language', sa.String(), server_default='ru', nullable=False))


def downgrade() -> None:
    op.drop_column('telegram_subscribers', 'language')
