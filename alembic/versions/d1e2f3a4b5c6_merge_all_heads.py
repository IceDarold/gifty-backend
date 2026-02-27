"""merge all remaining heads

Revision ID: d1e2f3a4b5c6
Revises: 0001_init_oauth, 77b8e12855d2, a1b2c3d4e5f6, b7a1e2d3c4f5, b8d0b0b376d9, e5895b01411f, f2c1a3b4c5d6
Create Date: 2026-02-27

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = (
    "0001_init_oauth",
    "77b8e12855d2",
    "a1b2c3d4e5f6",
    "b7a1e2d3c4f5",
    "b8d0b0b376d9",
    "e5895b01411f",
    "f2c1a3b4c5d6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge-only revision: no schema changes.
    pass


def downgrade() -> None:
    # Merge-only revision: no schema changes.
    pass

