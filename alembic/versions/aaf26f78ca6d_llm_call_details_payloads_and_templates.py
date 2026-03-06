"""llm call details payloads and templates

Revision ID: aaf26f78ca6d
Revises: 1ea3169488c4
Create Date: 2026-03-06 18:13:58.210271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'aaf26f78ca6d'
down_revision: Union[str, None] = '1ea3169488c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("template_hash", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", "template_hash", name="uq_llm_prompt_templates_name_hash"),
    )
    op.create_index(op.f("ix_llm_prompt_templates_name"), "llm_prompt_templates", ["name"], unique=False)
    op.create_index(op.f("ix_llm_prompt_templates_kind"), "llm_prompt_templates", ["kind"], unique=False)
    op.create_index(op.f("ix_llm_prompt_templates_template_hash"), "llm_prompt_templates", ["template_hash"], unique=False)

    op.create_table(
        "llm_payloads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_payloads")),
        sa.UniqueConstraint("sha256", name="uq_llm_payloads_sha256"),
        sa.CheckConstraint(
            "(content_text IS NOT NULL) <> (content_json IS NOT NULL)",
            name="ck_llm_payloads_exactly_one_content",
        ),
    )
    op.create_index(op.f("ix_llm_payloads_kind"), "llm_payloads", ["kind"], unique=False)
    op.create_index(op.f("ix_llm_payloads_sha256"), "llm_payloads", ["sha256"], unique=False)

    op.add_column("llm_logs", sa.Column("system_prompt_template_id", sa.Integer(), nullable=True))
    op.add_column("llm_logs", sa.Column("system_prompt_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("llm_logs", sa.Column("user_prompt_template_id", sa.Integer(), nullable=True))
    op.add_column("llm_logs", sa.Column("user_prompt_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("llm_logs", sa.Column("output_payload_id", sa.UUID(), nullable=True))
    op.add_column("llm_logs", sa.Column("raw_response_payload_id", sa.UUID(), nullable=True))
    op.add_column("llm_logs", sa.Column("finish_reason", sa.String(), nullable=True))
    op.add_column("llm_logs", sa.Column("provider_latency_ms", sa.Integer(), nullable=True))
    op.add_column("llm_logs", sa.Column("queue_latency_ms", sa.Integer(), nullable=True))
    op.add_column("llm_logs", sa.Column("postprocess_latency_ms", sa.Integer(), nullable=True))

    op.create_index(op.f("ix_llm_logs_system_prompt_template_id"), "llm_logs", ["system_prompt_template_id"], unique=False)
    op.create_index(op.f("ix_llm_logs_user_prompt_template_id"), "llm_logs", ["user_prompt_template_id"], unique=False)
    op.create_index(op.f("ix_llm_logs_output_payload_id"), "llm_logs", ["output_payload_id"], unique=False)
    op.create_index(op.f("ix_llm_logs_raw_response_payload_id"), "llm_logs", ["raw_response_payload_id"], unique=False)
    op.create_index(op.f("ix_llm_logs_finish_reason"), "llm_logs", ["finish_reason"], unique=False)

    op.create_foreign_key(
        "fk_llm_logs_system_prompt_template_id",
        "llm_logs",
        "llm_prompt_templates",
        ["system_prompt_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_logs_user_prompt_template_id",
        "llm_logs",
        "llm_prompt_templates",
        ["user_prompt_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_logs_output_payload_id",
        "llm_logs",
        "llm_payloads",
        ["output_payload_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_logs_raw_response_payload_id",
        "llm_logs",
        "llm_payloads",
        ["raw_response_payload_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_llm_logs_raw_response_payload_id", "llm_logs", type_="foreignkey")
    op.drop_constraint("fk_llm_logs_output_payload_id", "llm_logs", type_="foreignkey")
    op.drop_constraint("fk_llm_logs_user_prompt_template_id", "llm_logs", type_="foreignkey")
    op.drop_constraint("fk_llm_logs_system_prompt_template_id", "llm_logs", type_="foreignkey")

    op.drop_index(op.f("ix_llm_logs_finish_reason"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_raw_response_payload_id"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_output_payload_id"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_user_prompt_template_id"), table_name="llm_logs")
    op.drop_index(op.f("ix_llm_logs_system_prompt_template_id"), table_name="llm_logs")

    op.drop_column("llm_logs", "postprocess_latency_ms")
    op.drop_column("llm_logs", "queue_latency_ms")
    op.drop_column("llm_logs", "provider_latency_ms")
    op.drop_column("llm_logs", "finish_reason")
    op.drop_column("llm_logs", "raw_response_payload_id")
    op.drop_column("llm_logs", "output_payload_id")
    op.drop_column("llm_logs", "user_prompt_params")
    op.drop_column("llm_logs", "user_prompt_template_id")
    op.drop_column("llm_logs", "system_prompt_params")
    op.drop_column("llm_logs", "system_prompt_template_id")

    op.drop_index(op.f("ix_llm_payloads_sha256"), table_name="llm_payloads")
    op.drop_index(op.f("ix_llm_payloads_kind"), table_name="llm_payloads")
    op.drop_table("llm_payloads")

    op.drop_index(op.f("ix_llm_prompt_templates_template_hash"), table_name="llm_prompt_templates")
    op.drop_index(op.f("ix_llm_prompt_templates_kind"), table_name="llm_prompt_templates")
    op.drop_index(op.f("ix_llm_prompt_templates_name"), table_name="llm_prompt_templates")
    op.drop_table("llm_prompt_templates")
