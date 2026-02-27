"""products_product_id_merchants_category_links

Revision ID: b8d0b0b376d9
Revises: f4b2c9d8e7a1
Create Date: 2026-02-25 20:11:22.015149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b8d0b0b376d9'
down_revision: Union[str, None] = 'f4b2c9d8e7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Rename products.gift_id -> products.product_id
    op.alter_column("products", "gift_id", new_column_name="product_id")

    # 2) Add products.site_key (best-effort backfill from product_id prefix)
    op.add_column("products", sa.Column("site_key", sa.String(), nullable=True))
    op.execute("UPDATE products SET site_key = split_part(product_id, ':', 1) WHERE site_key IS NULL")
    op.create_index(op.f("ix_products_site_key"), "products", ["site_key"], unique=False)

    # 3) Rename product_embeddings.gift_id -> product_embeddings.product_id
    op.alter_column("product_embeddings", "gift_id", new_column_name="product_id")

    # Drop old FK name (naming convention still references gift_id)
    with op.batch_alter_table("product_embeddings") as batch:
        batch.drop_constraint("fk_product_embeddings_gift_id_products", type_="foreignkey")
        batch.create_foreign_key(
            "fk_product_embeddings_product_id_products",
            "products",
            ["product_id"],
            ["product_id"],
            ondelete="CASCADE",
        )

    # 4) Merchants table (store metadata, linked by site_key)
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("site_key", name="uq_merchants_site_key"),
    )
    op.create_index(op.f("ix_merchants_site_key"), "merchants", ["site_key"], unique=True)

    # Seed merchants from existing parsing sources/hubs
    op.execute(
        """
        INSERT INTO merchants (site_key, name)
        SELECT DISTINCT s.site_key, s.site_key
        FROM (
            SELECT site_key FROM parsing_sources WHERE site_key IS NOT NULL
            UNION
            SELECT site_key FROM parsing_hubs WHERE site_key IS NOT NULL
        ) s
        ON CONFLICT (site_key) DO NOTHING
        """
    )

    # 5) Product <-> DiscoveredCategory links (external category provenance)
    op.create_table(
        "product_category_links",
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("discovered_category_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("last_run_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("seen_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Keep names short: Postgres identifier length limit is 63 chars.
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE", name="fk_pcl_product"),
        sa.ForeignKeyConstraint(["discovered_category_id"], ["discovered_categories.id"], ondelete="CASCADE", name="fk_pcl_category"),
        sa.ForeignKeyConstraint(["source_id"], ["parsing_sources.id"], ondelete="SET NULL", name="fk_pcl_source"),
        sa.ForeignKeyConstraint(["last_run_id"], ["parsing_runs.id"], ondelete="SET NULL", name="fk_pcl_run"),
        sa.PrimaryKeyConstraint("product_id", "discovered_category_id", name="pk_product_category_links"),
    )
    op.create_index(op.f("ix_product_category_links_discovered_category_id"), "product_category_links", ["discovered_category_id"], unique=False)
    op.create_index(op.f("ix_product_category_links_source_id"), "product_category_links", ["source_id"], unique=False)
    op.create_index(op.f("ix_product_category_links_last_run_id"), "product_category_links", ["last_run_id"], unique=False)

    # 6) Remove LLM gift scoring columns from products (not needed now)
    # Drop index first if exists
    # Index may be missing in some environments (manual cleanup), so use IF EXISTS.
    op.execute("DROP INDEX IF EXISTS ix_products_llm_gift_score")
    for col in (
        "llm_gift_score",
        "llm_gift_reasoning",
        "llm_gift_vector",
        "llm_scoring_model",
        "llm_scoring_version",
        "llm_scored_at",
    ):
        op.drop_column("products", col)


def downgrade() -> None:
    # Drop link + merchant tables first (they reference products/categories)
    op.drop_index(op.f("ix_product_category_links_last_run_id"), table_name="product_category_links")
    op.drop_index(op.f("ix_product_category_links_source_id"), table_name="product_category_links")
    op.drop_index(op.f("ix_product_category_links_discovered_category_id"), table_name="product_category_links")
    op.drop_table("product_category_links")

    op.drop_index(op.f("ix_merchants_site_key"), table_name="merchants")
    op.drop_table("merchants")

    # Revert product_embeddings FK + column rename (must happen after dropping FK)
    with op.batch_alter_table("product_embeddings") as batch:
        batch.drop_constraint("fk_product_embeddings_product_id_products", type_="foreignkey")

    op.alter_column("product_embeddings", "product_id", new_column_name="gift_id")

    # Revert products.site_key and primary id column rename
    op.drop_index(op.f("ix_products_site_key"), table_name="products")
    op.drop_column("products", "site_key")
    op.alter_column("products", "product_id", new_column_name="gift_id")

    # Recreate FK with original naming convention
    with op.batch_alter_table("product_embeddings") as batch:
        batch.create_foreign_key(
            "fk_product_embeddings_gift_id_products",
            "products",
            ["gift_id"],
            ["gift_id"],
            ondelete="CASCADE",
        )

    # Re-add LLM scoring columns + index
    op.add_column("products", sa.Column("llm_scored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("llm_scoring_version", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("llm_scoring_model", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("llm_gift_reasoning", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("llm_gift_score", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("llm_gift_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index(op.f("ix_products_llm_gift_score"), "products", ["llm_gift_score"], unique=False)
