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
    # This migration can be applied on environments where some of the columns/indexes
    # were created manually or by previous hotfixes. Make it idempotent.
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_tables = set(insp.get_table_names())
    if "llm_logs" not in existing_tables:
        return

    existing_cols = {c.get("name") for c in insp.get_columns("llm_logs")}
    if "status" not in existing_cols:
        op.add_column("llm_logs", sa.Column("status", sa.String(), server_default="ok", nullable=False))
    if "error_type" not in existing_cols:
        op.add_column("llm_logs", sa.Column("error_type", sa.String(), nullable=True))
    if "error_message" not in existing_cols:
        op.add_column("llm_logs", sa.Column("error_message", sa.Text(), nullable=True))
    if "provider_request_id" not in existing_cols:
        op.add_column("llm_logs", sa.Column("provider_request_id", sa.String(), nullable=True))
    if "prompt_hash" not in existing_cols:
        op.add_column("llm_logs", sa.Column("prompt_hash", sa.String(), nullable=True))
    if "params" not in existing_cols:
        op.add_column("llm_logs", sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    existing_indexes = {i.get("name") for i in insp.get_indexes("llm_logs")}
    status_idx = op.f("ix_llm_logs_status")
    error_type_idx = op.f("ix_llm_logs_error_type")
    provider_request_id_idx = op.f("ix_llm_logs_provider_request_id")
    prompt_hash_idx = op.f("ix_llm_logs_prompt_hash")

    if status_idx not in existing_indexes and "status" in {c.get("name") for c in insp.get_columns("llm_logs")}:
        op.create_index(status_idx, "llm_logs", ["status"], unique=False)
    if error_type_idx not in existing_indexes and "error_type" in {c.get("name") for c in insp.get_columns("llm_logs")}:
        op.create_index(error_type_idx, "llm_logs", ["error_type"], unique=False)
    if provider_request_id_idx not in existing_indexes and "provider_request_id" in {c.get("name") for c in insp.get_columns("llm_logs")}:
        op.create_index(provider_request_id_idx, "llm_logs", ["provider_request_id"], unique=False)
    if prompt_hash_idx not in existing_indexes and "prompt_hash" in {c.get("name") for c in insp.get_columns("llm_logs")}:
        op.create_index(prompt_hash_idx, "llm_logs", ["prompt_hash"], unique=False)


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
