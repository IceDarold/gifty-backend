"""add logs to parsing_runs

Revision ID: f9c4b8e1a2d0
Revises: d6308a1fcec9
Create Date: 2026-02-22 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9c4b8e1a2d0"
down_revision: Union[str, None] = "d6308a1fcec9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parsing_runs", sa.Column("logs", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("parsing_runs", "logs")

