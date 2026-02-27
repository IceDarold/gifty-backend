"""add_search_logs_table

Revision ID: 77b8e12855d2
Revises: f2c1a3b4c5d6
Create Date: 2026-02-18 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError

# revision identifiers, used by Alembic.
revision = '77b8e12855d2'
down_revision = 'cf54215d5932' # cf54215d5932_add_compute_tasks_table.py seems latest or near it
branch_labels = None
depends_on = None

def upgrade():
    """
    This migration might be applied on environments where the tables already exist
    (e.g. created manually or via a previous hotfix without Alembic stamp).
    Make it idempotent: skip create if the target object already exists.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "search_logs" not in existing_tables:
        op.create_table(
            "search_logs",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("track_title", sa.String(), nullable=True),
            sa.Column("hypothesis_title", sa.String(), nullable=True),
            sa.Column("search_context", sa.String(), nullable=True),
            sa.Column("llm_model", sa.String(), nullable=True),
            sa.Column("search_query", sa.Text(), nullable=False),
            sa.Column("results_count", sa.Integer(), nullable=False),
            sa.Column("avg_similarity", sa.Float(), nullable=True),
            sa.Column("top_similarity", sa.Float(), nullable=True),
            sa.Column("top_gift_id", sa.Text(), nullable=True),
            sa.Column("max_price", sa.Integer(), nullable=True),
            sa.Column("execution_time_ms", sa.Integer(), nullable=True),
            sa.Column("engine_version", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # Indexes: best-effort; tolerate existing.
    for idx_name, cols in (
        (op.f("ix_search_logs_hypothesis_id"), ["hypothesis_id"]),
        (op.f("ix_search_logs_session_id"), ["session_id"]),
    ):
        try:
            op.create_index(idx_name, "search_logs", cols, unique=False)
        except ProgrammingError:
            pass

    if "hypothesis_product_links" not in existing_tables:
        op.create_table(
            "hypothesis_product_links",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("gift_id", sa.String(), nullable=False),
            sa.Column("similarity_score", sa.Float(), nullable=False),
            sa.Column("rank_position", sa.Integer(), nullable=False),
            sa.Column("was_shown", sa.Boolean(), nullable=False),
            sa.Column("was_clicked", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for idx_name, cols in (
        (op.f("ix_hypothesis_product_links_gift_id"), ["gift_id"]),
        (op.f("ix_hypothesis_product_links_hypothesis_id"), ["hypothesis_id"]),
    ):
        try:
            op.create_index(idx_name, "hypothesis_product_links", cols, unique=False)
        except ProgrammingError:
            pass

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "hypothesis_product_links" in existing_tables:
        for idx_name in (
            op.f("ix_hypothesis_product_links_gift_id"),
            op.f("ix_hypothesis_product_links_hypothesis_id"),
        ):
            try:
                op.drop_index(idx_name, table_name="hypothesis_product_links")
            except ProgrammingError:
                pass
        try:
            op.drop_table("hypothesis_product_links")
        except ProgrammingError:
            pass

    if "search_logs" in existing_tables:
        for idx_name in (op.f("ix_search_logs_session_id"), op.f("ix_search_logs_hypothesis_id")):
            try:
                op.drop_index(idx_name, table_name="search_logs")
            except ProgrammingError:
                pass
        try:
            op.drop_table("search_logs")
        except ProgrammingError:
            pass
