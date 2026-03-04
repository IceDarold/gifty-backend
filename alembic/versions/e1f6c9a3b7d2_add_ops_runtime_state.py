"""add ops runtime state

Revision ID: e1f6c9a3b7d2
Revises: c3d9a4e7b2f1
Create Date: 2026-02-25 11:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f6c9a3b7d2"
down_revision: Union[str, None] = "c3d9a4e7b2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ops_runtime_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheduler_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(
        """
        INSERT INTO ops_runtime_state (id, scheduler_paused)
        VALUES (1, false)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("ops_runtime_state")
