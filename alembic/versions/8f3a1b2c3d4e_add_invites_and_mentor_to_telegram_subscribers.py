"""add invites and mentor to telegram_subscribers

Revision ID: 8f3a1b2c3d4e
Revises: e5895b01411f
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8f3a1b2c3d4e"
down_revision = "e5895b01411f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_subscribers", sa.Column("invite_password_hash", sa.Text(), nullable=True))
    op.add_column("telegram_subscribers", sa.Column("mentor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_telegram_subscribers_mentor_id",
        "telegram_subscribers",
        "telegram_subscribers",
        ["mentor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "telegram_subscribers",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "telegram_subscribers",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_constraint("fk_telegram_subscribers_mentor_id", "telegram_subscribers", type_="foreignkey")
    op.drop_column("telegram_subscribers", "mentor_id")
    op.drop_column("telegram_subscribers", "invite_password_hash")
