"""add outbox events

Revision ID: a9d1c4e5f6b7
Revises: c3d9a4e7b2f1
Create Date: 2026-03-11 23:45:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a9d1c4e5f6b7'
down_revision = 'c3d9a4e7b2f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('aggregate_type', sa.String(), nullable=False),
        sa.Column('aggregate_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('headers_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
    )
    op.create_index('ix_outbox_events_aggregate_type', 'outbox_events', ['aggregate_type'])
    op.create_index('ix_outbox_events_aggregate_id', 'outbox_events', ['aggregate_id'])
    op.create_index('ix_outbox_events_event_type', 'outbox_events', ['event_type'])
    op.create_index('ix_outbox_events_created_at', 'outbox_events', ['created_at'])
    op.create_index('ix_outbox_events_published_at', 'outbox_events', ['published_at'])


def downgrade() -> None:
    op.drop_index('ix_outbox_events_published_at', table_name='outbox_events')
    op.drop_index('ix_outbox_events_created_at', table_name='outbox_events')
    op.drop_index('ix_outbox_events_event_type', table_name='outbox_events')
    op.drop_index('ix_outbox_events_aggregate_id', table_name='outbox_events')
    op.drop_index('ix_outbox_events_aggregate_type', table_name='outbox_events')
    op.drop_table('outbox_events')
