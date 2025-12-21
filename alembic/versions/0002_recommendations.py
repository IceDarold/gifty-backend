"""add recommendation persistence tables

Revision ID: 0002_recommendations
Revises: 0001_init_oauth
Create Date: 2024-05-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_recommendations"
down_revision = "0001_init_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("anon_id", sa.String(), nullable=True),
        sa.Column("answers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quiz_runs_user_id", "quiz_runs", ["user_id"], unique=False)
    op.create_index("ix_quiz_runs_anon_id", "quiz_runs", ["anon_id"], unique=False)

    op.create_table(
        "recommendation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "quiz_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quiz_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("featured_gift_id", sa.String(), nullable=False),
        sa.Column("gift_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("debug_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_recommendation_runs_quiz_run_id",
        "recommendation_runs",
        ["quiz_run_id"],
        unique=False,
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("anon_id", sa.String(), nullable=True),
        sa.Column("quiz_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quiz_runs.id"), nullable=True),
        sa.Column(
            "recommendation_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recommendation_runs.id"),
            nullable=True,
        ),
        sa.Column("gift_id", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"], unique=False)
    op.create_index("ix_events_anon_id", "events", ["anon_id"], unique=False)
    op.create_index("ix_events_quiz_run_id", "events", ["quiz_run_id"], unique=False)
    op.create_index(
        "ix_events_recommendation_run_id",
        "events",
        ["recommendation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_events_recommendation_run_id", table_name="events")
    op.drop_index("ix_events_quiz_run_id", table_name="events")
    op.drop_index("ix_events_anon_id", table_name="events")
    op.drop_index("ix_events_user_id", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_recommendation_runs_quiz_run_id", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")

    op.drop_index("ix_quiz_runs_anon_id", table_name="quiz_runs")
    op.drop_index("ix_quiz_runs_user_id", table_name="quiz_runs")
    op.drop_table("quiz_runs")
