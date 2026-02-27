"""expand ops runtime state

Revision ID: f4b2c9d8e7a1
Revises: e1f6c9a3b7d2
Create Date: 2026-02-25 13:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4b2c9d8e7a1"
down_revision: Union[str, None] = "e1f6c9a3b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ops_runtime_state", sa.Column("settings_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("ops_runtime_state", sa.Column("ops_aggregator_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("ops_runtime_state", sa.Column("ops_aggregator_interval_ms", sa.Integer(), nullable=False, server_default="2000"))
    op.add_column("ops_runtime_state", sa.Column("ops_snapshot_ttl_ms", sa.Integer(), nullable=False, server_default="10000"))
    op.add_column("ops_runtime_state", sa.Column("ops_stale_max_age_ms", sa.Integer(), nullable=False, server_default="60000"))
    op.add_column("ops_runtime_state", sa.Column("ops_client_intervals", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("ops_runtime_state", sa.Column("updated_by", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("ops_runtime_state", "updated_by")
    op.drop_column("ops_runtime_state", "ops_client_intervals")
    op.drop_column("ops_runtime_state", "ops_stale_max_age_ms")
    op.drop_column("ops_runtime_state", "ops_snapshot_ttl_ms")
    op.drop_column("ops_runtime_state", "ops_aggregator_interval_ms")
    op.drop_column("ops_runtime_state", "ops_aggregator_enabled")
    op.drop_column("ops_runtime_state", "settings_version")
