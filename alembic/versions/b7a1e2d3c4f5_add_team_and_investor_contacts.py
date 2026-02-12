"""add_team_and_investor_contacts

Revision ID: b7a1e2d3c4f5
Revises: 041553a0e7bb
Create Date: 2026-02-08 20:18:45.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7a1e2d3c4f5'
down_revision = '041553a0e7bb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create team_members table
    op.create_table(
        'team_members',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.String(), nullable=True),
        sa.Column('photo_public_id', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_team_members_is_active'), 'team_members', ['is_active'], unique=False)
    op.create_index(op.f('ix_team_members_sort_order'), 'team_members', ['sort_order'], unique=False)

    # Create investor_contacts table
    op.create_table(
        'investor_contacts',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('company', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('linkedin_url', sa.String(), nullable=True),
        sa.Column('ip', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investor_contacts_email'), 'investor_contacts', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_investor_contacts_email'), table_name='investor_contacts')
    op.drop_table('investor_contacts')
    op.drop_index(op.f('ix_team_members_sort_order'), table_name='team_members')
    op.drop_index(op.f('ix_team_members_is_active'), table_name='team_members')
    op.drop_table('team_members')
