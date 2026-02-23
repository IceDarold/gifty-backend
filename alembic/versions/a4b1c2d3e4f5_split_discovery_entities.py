"""split discovery entities into hubs and discovered categories

Revision ID: a4b1c2d3e4f5
Revises: f9c4b8e1a2d0
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a4b1c2d3e4f5"
down_revision: Union[str, None] = "f9c4b8e1a2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parsing_hubs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("strategy", sa.String(), server_default="discovery", nullable=False),
        sa.Column("refresh_interval_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("status", sa.String(), server_default="waiting", nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_key", name="uq_parsing_hubs_site_key"),
    )
    op.create_index(op.f("ix_parsing_hubs_is_active"), "parsing_hubs", ["is_active"], unique=False)
    op.create_index(op.f("ix_parsing_hubs_next_sync_at"), "parsing_hubs", ["next_sync_at"], unique=False)
    op.create_index(op.f("ix_parsing_hubs_site_key"), "parsing_hubs", ["site_key"], unique=False)
    op.create_index(op.f("ix_parsing_hubs_status"), "parsing_hubs", ["status"], unique=False)

    op.create_table(
        "discovered_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hub_id", sa.Integer(), nullable=True),
        sa.Column("site_key", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("parent_url", sa.Text(), nullable=True),
        sa.Column("state", sa.String(), server_default="new", nullable=False),
        sa.Column("promoted_source_id", sa.Integer(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hub_id"], ["parsing_hubs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["promoted_source_id"], ["parsing_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_key", "url", name="uq_discovered_categories_site_url"),
    )
    op.create_index(op.f("ix_discovered_categories_hub_id"), "discovered_categories", ["hub_id"], unique=False)
    op.create_index(op.f("ix_discovered_categories_promoted_source_id"), "discovered_categories", ["promoted_source_id"], unique=False)
    op.create_index(op.f("ix_discovered_categories_site_key"), "discovered_categories", ["site_key"], unique=False)
    op.create_index(op.f("ix_discovered_categories_state"), "discovered_categories", ["state"], unique=False)

    op.add_column("parsing_sources", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_parsing_sources_category_id"), "parsing_sources", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_parsing_sources_category_id_discovered_categories",
        "parsing_sources",
        "discovered_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill hubs from legacy parsing_sources(type='hub')
    op.execute(
        """
        INSERT INTO parsing_hubs (site_key, name, url, strategy, refresh_interval_hours, last_synced_at, next_sync_at, is_active, status, config, created_at, updated_at)
        SELECT
            site_key,
            NULL::varchar as name,
            min(url) as url,
            'discovery' as strategy,
            COALESCE(min(refresh_interval_hours), 24) as refresh_interval_hours,
            max(last_synced_at) as last_synced_at,
            COALESCE(min(next_sync_at), now()) as next_sync_at,
            bool_or(is_active) as is_active,
            CASE
                WHEN bool_or(status = 'running') THEN 'running'
                WHEN bool_or(status = 'queued') THEN 'queued'
                WHEN bool_or(status = 'error') THEN 'error'
                WHEN bool_or(status = 'broken') THEN 'broken'
                ELSE 'waiting'
            END as status,
            jsonb_build_object('migrated_from_parsing_sources', true) as config,
            min(created_at) as created_at,
            max(updated_at) as updated_at
        FROM parsing_sources
        WHERE type = 'hub'
        GROUP BY site_key
        ON CONFLICT (site_key) DO NOTHING
        """
    )

    # Backfill discovered categories from legacy list sources
    op.execute(
        """
        INSERT INTO discovered_categories (
            hub_id, site_key, url, name, parent_url, state, promoted_source_id, meta, created_at, updated_at
        )
        SELECT
            h.id as hub_id,
            s.site_key,
            s.url,
            s.config->>'discovery_name' as name,
            s.config->>'parent_url' as parent_url,
            CASE WHEN s.is_active THEN 'promoted' ELSE 'new' END as state,
            s.id as promoted_source_id,
            jsonb_build_object('migrated_from_source_id', s.id) as meta,
            s.created_at,
            s.updated_at
        FROM parsing_sources s
        LEFT JOIN parsing_hubs h ON h.site_key = s.site_key
        WHERE s.type = 'list'
        ON CONFLICT (site_key, url) DO NOTHING
        """
    )

    # Link runtime sources back to discovered categories
    op.execute(
        """
        UPDATE parsing_sources s
        SET category_id = dc.id
        FROM discovered_categories dc
        WHERE s.type = 'list'
          AND s.site_key = dc.site_key
          AND s.url = dc.url
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_parsing_sources_category_id_discovered_categories", "parsing_sources", type_="foreignkey")
    op.drop_index(op.f("ix_parsing_sources_category_id"), table_name="parsing_sources")
    op.drop_column("parsing_sources", "category_id")

    op.drop_index(op.f("ix_discovered_categories_state"), table_name="discovered_categories")
    op.drop_index(op.f("ix_discovered_categories_site_key"), table_name="discovered_categories")
    op.drop_index(op.f("ix_discovered_categories_promoted_source_id"), table_name="discovered_categories")
    op.drop_index(op.f("ix_discovered_categories_hub_id"), table_name="discovered_categories")
    op.drop_table("discovered_categories")

    op.drop_index(op.f("ix_parsing_hubs_status"), table_name="parsing_hubs")
    op.drop_index(op.f("ix_parsing_hubs_site_key"), table_name="parsing_hubs")
    op.drop_index(op.f("ix_parsing_hubs_next_sync_at"), table_name="parsing_hubs")
    op.drop_index(op.f("ix_parsing_hubs_is_active"), table_name="parsing_hubs")
    op.drop_table("parsing_hubs")
