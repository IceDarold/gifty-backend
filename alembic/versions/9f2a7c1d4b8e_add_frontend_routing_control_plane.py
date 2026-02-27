"""add frontend routing control plane

Revision ID: 9f2a7c1d4b8e
Revises: f9c4b8e1a2d0
Create Date: 2026-02-23 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9f2a7c1d4b8e"
# NOTE: keep a valid down_revision present in this repo. This revision was introduced via cherry-pick
# and originally referenced a non-existent placeholder revision.
down_revision: Union[str, None] = "cf54215d5932"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "frontend_apps",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.UniqueConstraint("key", name="uq_frontend_apps_key"),
    )
    op.create_index(op.f("ix_frontend_apps_key"), "frontend_apps", ["key"], unique=False)
    op.create_index(op.f("ix_frontend_apps_is_active"), "frontend_apps", ["is_active"], unique=False)

    op.create_table(
        "frontend_releases",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("frontend_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("health_status", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("flags", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("app_id", "version", name="uq_frontend_releases_app_version"),
    )
    op.create_index(op.f("ix_frontend_releases_app_id"), "frontend_releases", ["app_id"], unique=False)
    op.create_index(op.f("ix_frontend_releases_status"), "frontend_releases", ["status"], unique=False)
    op.create_index(op.f("ix_frontend_releases_health_status"), "frontend_releases", ["health_status"], unique=False)

    op.create_table(
        "frontend_profiles",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.UniqueConstraint("key", name="uq_frontend_profiles_key"),
    )
    op.create_index(op.f("ix_frontend_profiles_key"), "frontend_profiles", ["key"], unique=False)
    op.create_index(op.f("ix_frontend_profiles_is_active"), "frontend_profiles", ["is_active"], unique=False)

    op.create_table(
        "frontend_rules",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("frontend_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("host_pattern", sa.String(), nullable=False, server_default="*"),
        sa.Column("path_pattern", sa.String(), nullable=False, server_default="/*"),
        sa.Column("query_conditions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("target_release_id", sa.Integer(), sa.ForeignKey("frontend_releases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("flags_override", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index(op.f("ix_frontend_rules_profile_id"), "frontend_rules", ["profile_id"], unique=False)
    op.create_index(op.f("ix_frontend_rules_target_release_id"), "frontend_rules", ["target_release_id"], unique=False)
    op.create_index(op.f("ix_frontend_rules_is_active"), "frontend_rules", ["is_active"], unique=False)
    op.create_index("ix_frontend_rules_profile_active_priority", "frontend_rules", ["profile_id", "is_active", "priority"], unique=False)

    op.create_table(
        "frontend_runtime_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_profile_id", sa.Integer(), sa.ForeignKey("frontend_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fallback_release_id", sa.Integer(), sa.ForeignKey("frontend_releases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sticky_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sticky_ttl_seconds", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "frontend_allowed_hosts",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint("host", name="uq_frontend_allowed_hosts_host"),
    )
    op.create_index(op.f("ix_frontend_allowed_hosts_host"), "frontend_allowed_hosts", ["host"], unique=False)
    op.create_index(op.f("ix_frontend_allowed_hosts_is_active"), "frontend_allowed_hosts", ["is_active"], unique=False)

    op.create_table(
        "frontend_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_frontend_audit_log_actor_id"), "frontend_audit_log", ["actor_id"], unique=False)
    op.create_index(op.f("ix_frontend_audit_log_action"), "frontend_audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_frontend_audit_log_entity_type"), "frontend_audit_log", ["entity_type"], unique=False)
    op.create_index(op.f("ix_frontend_audit_log_created_at"), "frontend_audit_log", ["created_at"], unique=False)

    op.execute(
        """
        INSERT INTO frontend_profiles (key, name, is_active)
        VALUES
            ('main', 'Main', true),
            ('campaign', 'Campaign', true),
            ('maintenance', 'Maintenance', true)
        """
    )
    op.execute(
        """
        INSERT INTO frontend_runtime_state (id, active_profile_id, sticky_enabled, sticky_ttl_seconds, cache_ttl_seconds)
        VALUES (1, (SELECT id FROM frontend_profiles WHERE key = 'main'), true, 1800, 15)
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_frontend_audit_log_created_at"), table_name="frontend_audit_log")
    op.drop_index(op.f("ix_frontend_audit_log_entity_type"), table_name="frontend_audit_log")
    op.drop_index(op.f("ix_frontend_audit_log_action"), table_name="frontend_audit_log")
    op.drop_index(op.f("ix_frontend_audit_log_actor_id"), table_name="frontend_audit_log")
    op.drop_table("frontend_audit_log")

    op.drop_index(op.f("ix_frontend_allowed_hosts_is_active"), table_name="frontend_allowed_hosts")
    op.drop_index(op.f("ix_frontend_allowed_hosts_host"), table_name="frontend_allowed_hosts")
    op.drop_table("frontend_allowed_hosts")

    op.drop_table("frontend_runtime_state")

    op.drop_index("ix_frontend_rules_profile_active_priority", table_name="frontend_rules")
    op.drop_index(op.f("ix_frontend_rules_is_active"), table_name="frontend_rules")
    op.drop_index(op.f("ix_frontend_rules_target_release_id"), table_name="frontend_rules")
    op.drop_index(op.f("ix_frontend_rules_profile_id"), table_name="frontend_rules")
    op.drop_table("frontend_rules")

    op.drop_index(op.f("ix_frontend_profiles_is_active"), table_name="frontend_profiles")
    op.drop_index(op.f("ix_frontend_profiles_key"), table_name="frontend_profiles")
    op.drop_table("frontend_profiles")

    op.drop_index(op.f("ix_frontend_releases_health_status"), table_name="frontend_releases")
    op.drop_index(op.f("ix_frontend_releases_status"), table_name="frontend_releases")
    op.drop_index(op.f("ix_frontend_releases_app_id"), table_name="frontend_releases")
    op.drop_table("frontend_releases")

    op.drop_index(op.f("ix_frontend_apps_is_active"), table_name="frontend_apps")
    op.drop_index(op.f("ix_frontend_apps_key"), table_name="frontend_apps")
    op.drop_table("frontend_apps")
