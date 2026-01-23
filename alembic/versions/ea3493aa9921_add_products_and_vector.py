"""add_products_and_vector

Revision ID: ea3493aa9921
Revises: 0002_recommendations
Create Date: 2025-12-24 02:04:34.753940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea3493aa9921'
down_revision: Union[str, None] = '0002_recommendations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create products table
    op.create_table('products',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('gift_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(), nullable=True),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('product_url', sa.Text(), nullable=False),
        sa.Column('merchant', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('raw', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('gift_id')
    )
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index(op.f('ix_products_is_active'), 'products', ['is_active'], unique=False)
    op.create_index(op.f('ix_products_merchant'), 'products', ['merchant'], unique=False)

    # 3. Create product_embeddings table
    op.create_table('product_embeddings',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('gift_id', sa.Text(), nullable=False),
        sa.Column('model_name', sa.Text(), nullable=False),
        sa.Column('model_version', sa.Text(), nullable=False),
        sa.Column('dim', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('embedded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('gift_id', 'model_name', 'model_version'),
        sa.ForeignKeyConstraint(['gift_id'], ['products.gift_id'], ondelete='CASCADE')
    )
    
    # Add vector column via raw SQL to avoid needing pgvector types in python env during migration gen
    # Assuming BAAI/bge-m3 dimension is 1024
    op.execute("ALTER TABLE product_embeddings ADD COLUMN embedding vector(1024)")
    
    # Create HNSW index for cosine similarity
    # Note: access method 'hnsw' requires pgvector
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_product_embeddings_embedding 
        ON product_embeddings 
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.drop_table('product_embeddings')
    op.drop_index(op.f('ix_products_merchant'), table_name='products')
    op.drop_index(op.f('ix_products_is_active'), table_name='products')
    op.drop_index(op.f('ix_products_category'), table_name='products')
    op.drop_table('products')
    op.execute("DROP EXTENSION IF EXISTS vector")
