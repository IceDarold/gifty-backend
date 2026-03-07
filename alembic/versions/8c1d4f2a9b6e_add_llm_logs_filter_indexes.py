"""bridge llm log index revision

Revision ID: 8c1d4f2a9b6e
Revises: 49760187d375
Create Date: 2026-03-07 00:00:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "8c1d4f2a9b6e"
down_revision: Union[str, None] = "49760187d375"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
