"""add_parsing_tables

Revision ID: 041553a0e7bb
Revises: 67f5a0418824
Create Date: 2026-01-30 12:43:39.818767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '041553a0e7bb'
down_revision: Union[str, None] = '67f5a0418824'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'parsing_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('site_key', sa.String(), nullable=False),
        sa.Column('strategy', sa.String(), server_default='deep', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='50', nullable=False),
        sa.Column('refresh_interval_hours', sa.Integer(), server_default='24', nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_sync_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('config', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index(op.f('ix_parsing_sources_is_active'), 'parsing_sources', ['is_active'], unique=False)
    op.create_index(op.f('ix_parsing_sources_next_sync_at'), 'parsing_sources', ['next_sync_at'], unique=False)
    op.create_index(op.f('ix_parsing_sources_priority'), 'parsing_sources', ['priority'], unique=False)
    op.create_index(op.f('ix_parsing_sources_site_key'), 'parsing_sources', ['site_key'], unique=False)

    op.create_table(
        'category_maps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_name', sa.String(), nullable=False),
        sa.Column('internal_category_id', sa.Integer(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_name')
    )


def downgrade() -> None:
    op.drop_table('category_maps')
    op.drop_index(op.f('ix_parsing_sources_site_key'), table_name='parsing_sources')
    op.drop_index(op.f('ix_parsing_sources_priority'), table_name='parsing_sources')
    op.drop_index(op.f('ix_parsing_sources_next_sync_at'), table_name='parsing_sources')
    op.drop_index(op.f('ix_parsing_sources_is_active'), table_name='parsing_sources')
    op.drop_table('parsing_sources')
