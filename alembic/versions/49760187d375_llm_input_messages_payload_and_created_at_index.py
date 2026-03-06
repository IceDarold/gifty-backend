"""llm: input_messages payload ref + created_at index

Revision ID: 49760187d375
Revises: aaf26f78ca6d
Create Date: 2026-03-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "49760187d375"
down_revision: Union[str, None] = "aaf26f78ca6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "llm_logs" not in set(insp.get_table_names()):
        return

    existing_cols = {c.get("name") for c in insp.get_columns("llm_logs")}
    if "input_messages_payload_id" not in existing_cols:
        op.add_column("llm_logs", sa.Column("input_messages_payload_id", sa.UUID(), nullable=True))
        existing_cols.add("input_messages_payload_id")

    # Foreign key (idempotent by constrained columns)
    existing_fks = insp.get_foreign_keys("llm_logs")
    has_input_fk = any("input_messages_payload_id" in (fk.get("constrained_columns") or []) for fk in existing_fks)
    if not has_input_fk and "input_messages_payload_id" in existing_cols and "llm_payloads" in set(insp.get_table_names()):
        op.create_foreign_key(
            "fk_llm_logs_input_messages_payload_id_llm_payloads",
            "llm_logs",
            "llm_payloads",
            ["input_messages_payload_id"],
            ["id"],
            ondelete="SET NULL",
        )

    existing_indexes = {i.get("name") for i in insp.get_indexes("llm_logs")}
    idx_input = op.f("ix_llm_logs_input_messages_payload_id")
    if idx_input not in existing_indexes and "input_messages_payload_id" in existing_cols:
        op.create_index(idx_input, "llm_logs", ["input_messages_payload_id"], unique=False)

    idx_created = op.f("ix_llm_logs_created_at")
    if idx_created not in existing_indexes and "created_at" in existing_cols:
        op.create_index(idx_created, "llm_logs", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "llm_logs" not in set(insp.get_table_names()):
        return

    existing_cols = {c.get("name") for c in insp.get_columns("llm_logs")}
    existing_indexes = {i.get("name") for i in insp.get_indexes("llm_logs")}

    idx_created = op.f("ix_llm_logs_created_at")
    if idx_created in existing_indexes:
        op.drop_index(idx_created, table_name="llm_logs")

    idx_input = op.f("ix_llm_logs_input_messages_payload_id")
    if idx_input in existing_indexes:
        op.drop_index(idx_input, table_name="llm_logs")

    # Drop FK if present
    existing_fks = insp.get_foreign_keys("llm_logs")
    for fk in existing_fks:
        if "input_messages_payload_id" in (fk.get("constrained_columns") or []):
            fk_name = fk.get("name") or "fk_llm_logs_input_messages_payload_id_llm_payloads"
            try:
                op.drop_constraint(fk_name, "llm_logs", type_="foreignkey")
            except Exception:
                pass

    if "input_messages_payload_id" in existing_cols:
        op.drop_column("llm_logs", "input_messages_payload_id")

