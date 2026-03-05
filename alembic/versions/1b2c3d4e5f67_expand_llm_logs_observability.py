"""expand llm_logs observability fields

Revision ID: 1b2c3d4e5f67
Revises: f9c4b8e1a2d0
Create Date: 2026-03-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1b2c3d4e5f67"
down_revision: Union[str, None] = "f9c4b8e1a2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_logs", sa.Column("status", sa.String(), server_default="ok", nullable=False))
    op.add_column("llm_logs", sa.Column("error_type", sa.String(), nullable=True))
    op.add_column("llm_logs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("llm_logs", sa.Column("provider_request_id", sa.String(), nullable=True))
    op.add_column("llm_logs", sa.Column("prompt_hash", sa.String(), nullable=True))
    op.add_column("llm_logs", sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_index(op.f("ix_llm_logs_status"), "llm_logs", ["status"], unique=False)
    op.create_index(op.f("ix_llm_logs_error_type"), "llm_logs", ["error_type"], unique=False)
    op.create_index(op.f("ix_llm_logs_provider_request_id"), "llm_logs", ["provider_request_id"], unique=False)
    op.create_index(op.f("ix_llm_logs_prompt_hash"), "llm_logs", ["prompt_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_logs_prompt_hash"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_provider_request_id"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_error_type"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_status"), table_name="llm_logs")

    op.drop_column("llm_logs", "params")
    op.drop_column("llm_logs", "prompt_hash")
    op.drop_column("llm_logs", "provider_request_id")
    op.drop_column("llm_logs", "error_message")
    op.drop_column("llm_logs", "error_type")
    op.drop_column("llm_logs", "status")

