"""Add LLM scoring columns

Revision ID: 0005_llm_scoring
Revises: ea3493aa9921
Create Date: 2025-12-30 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_llm_scoring'
down_revision: Union[str, None] = 'ea3493aa9921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('llm_gift_score', sa.Float(), nullable=True))
    op.add_column('products', sa.Column('llm_gift_reasoning', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('llm_scoring_model', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('llm_scoring_version', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('llm_scored_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_products_llm_gift_score'), 'products', ['llm_gift_score'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_products_llm_gift_score'), table_name='products')
    op.drop_column('products', 'llm_scored_at')
    op.drop_column('products', 'llm_scoring_version')
    op.drop_column('products', 'llm_scoring_model')
    op.drop_column('products', 'llm_gift_reasoning')
    op.drop_column('products', 'llm_gift_score')
