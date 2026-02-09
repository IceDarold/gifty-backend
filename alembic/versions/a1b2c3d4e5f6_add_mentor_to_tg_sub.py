"""add mentor to telegram subscriber

Revision ID: a1b2c3d4e5f6
Revises: f2c1a3b4c5d6
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f2c1a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_subscribers", sa.Column("mentor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_telegram_subscribers_mentor_id",
        "telegram_subscribers",
        "telegram_subscribers",
        ["mentor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_telegram_subscribers_mentor_id", "telegram_subscribers", type_="foreignkey")
    op.drop_column("telegram_subscribers", "mentor_id")
