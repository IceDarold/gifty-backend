"""add llm logs query indexes

Revision ID: c3f9f4a6d2b1
Revises: 49760187d375
Create Date: 2026-03-07 10:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f9f4a6d2b1"
down_revision: Union[str, None] = "49760187d375"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = (
    ("ix_llm_logs_created_at_id", ["created_at", "id"]),
    ("ix_llm_logs_experiment_id_created_at", ["experiment_id", "created_at"]),
    ("ix_llm_logs_variant_id_created_at", ["variant_id", "created_at"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "llm_logs" not in set(inspector.get_table_names()):
        return

    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("llm_logs")}
    existing_columns = {column.get("name") for column in inspector.get_columns("llm_logs")}

    for index_name, columns in _INDEXES:
        if index_name in existing_indexes:
            continue
        if any(column not in existing_columns for column in columns):
            continue
        op.create_index(index_name, "llm_logs", columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "llm_logs" not in set(inspector.get_table_names()):
        return

    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("llm_logs")}
    for index_name, _columns in reversed(_INDEXES):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="llm_logs")
