"""remote head alias: merge parsing + llm_logs branches

This revision exists to support environments where the database was stamped
with an Alembic revision that no longer exists in the codebase (a063630851f9).

We recreate it as an empty merge revision so Alembic can locate it and
continue upgrading to the current head.

Revision ID: a063630851f9
Revises: 1b2c3d4e5f67, 8d5f0c2a9e11
Create Date: 2026-03-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "a063630851f9"
down_revision: Union[str, None] = ("1b2c3d4e5f67", "8d5f0c2a9e11")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

