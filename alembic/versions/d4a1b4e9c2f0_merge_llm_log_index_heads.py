"""merge llm log index heads

Revision ID: d4a1b4e9c2f0
Revises: 8c1d4f2a9b6e, c3f9f4a6d2b1
Create Date: 2026-03-07 00:00:01.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "d4a1b4e9c2f0"
down_revision: Union[str, Sequence[str], None] = ("8c1d4f2a9b6e", "c3f9f4a6d2b1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
