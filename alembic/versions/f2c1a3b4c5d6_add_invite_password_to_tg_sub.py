"""add invite password to telegram subscriber

Revision ID: f2c1a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f2c1a3b4c5d6"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_subscribers", sa.Column("invite_password_hash", sa.Text(), nullable=True))
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
    op.drop_column("telegram_subscribers", "invite_password_hash")
