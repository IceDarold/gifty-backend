"""ops invariants and discovery/runtime cleanup

Revision ID: c3d9a4e7b2f1
Revises: 9b6dcf704bbf
Create Date: 2026-02-23 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d9a4e7b2f1"
down_revision: Union[str, None] = "9b6dcf704bbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Ensure every runtime list source has a discovered category.
    op.execute(
        """
        INSERT INTO discovered_categories (
            hub_id,
            site_key,
            url,
            name,
            parent_url,
            state,
            promoted_source_id,
            meta,
            created_at,
            updated_at
        )
        SELECT
            h.id,
            s.site_key,
            s.url,
            COALESCE(s.config->>'discovery_name', NULL),
            COALESCE(s.config->>'parent_url', NULL),
            CASE WHEN s.is_active THEN 'promoted' ELSE 'inactive' END,
            s.id,
            jsonb_build_object('repair', true, 'reason', 'autocreated_from_runtime_source'),
            s.created_at,
            s.updated_at
        FROM parsing_sources s
        LEFT JOIN parsing_hubs h ON h.site_key = s.site_key
        LEFT JOIN discovered_categories dc ON dc.site_key = s.site_key AND dc.url = s.url
        WHERE s.type = 'list'
          AND dc.id IS NULL
        """
    )

    op.execute(
        """
        UPDATE parsing_sources s
        SET category_id = dc.id
        FROM discovered_categories dc
        WHERE s.type = 'list'
          AND s.category_id IS NULL
          AND s.site_key = dc.site_key
          AND s.url = dc.url
        """
    )

    # Keep promoted mapping consistent when runtime source exists.
    op.execute(
        """
        UPDATE discovered_categories dc
        SET promoted_source_id = s.id,
            state = 'promoted'
        FROM parsing_sources s
        WHERE s.type = 'list'
          AND s.category_id = dc.id
          AND (dc.promoted_source_id IS DISTINCT FROM s.id OR dc.state <> 'promoted')
        """
    )

    op.create_check_constraint(
        "ck_parsing_sources_list_requires_category",
        "parsing_sources",
        "type <> 'list' OR category_id IS NOT NULL",
    )

    op.create_check_constraint(
        "ck_discovered_categories_promoted_has_source",
        "discovered_categories",
        "state <> 'promoted' OR promoted_source_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_discovered_categories_promoted_has_source", "discovered_categories", type_="check")
    op.drop_constraint("ck_parsing_sources_list_requires_category", "parsing_sources", type_="check")
