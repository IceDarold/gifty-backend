"""add_telegram_subscriber

Revision ID: c8b2e3f4d5a6
Revises: b7a1e2d3c4f5
Create Date: 2026-02-08 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c8b2e3f4d5a6'
down_revision = 'b7a1e2d3c4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_subscribers',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('slug', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('subscriptions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_telegram_subscribers_chat_id'), 'telegram_subscribers', ['chat_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_telegram_subscribers_chat_id'), table_name='telegram_subscribers')
    op.drop_table('telegram_subscribers')
