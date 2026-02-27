"""initial oauth tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_init_oauth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: production may already have these tables created outside Alembic.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("avatar_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        )

    if "oauth_accounts" not in existing_tables:
        op.create_table(
            "oauth_accounts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("provider_user_id", sa.String(), nullable=False),
            sa.Column("email_at_provider", sa.String(), nullable=True),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_oauth_accounts_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_accounts")),
            sa.UniqueConstraint("provider", "provider_user_id", name=op.f("uq_oauth_accounts_provider_provider_user_id")),
        )

    if "oauth_accounts" in existing_tables:
        existing_indexes = {i.get("name") for i in insp.get_indexes("oauth_accounts")}
        if "ix_oauth_accounts_user_id" not in existing_indexes:
            op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "oauth_accounts" in existing_tables:
        existing_indexes = {i.get("name") for i in insp.get_indexes("oauth_accounts")}
        if "ix_oauth_accounts_user_id" in existing_indexes:
            op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
        op.drop_table("oauth_accounts")
    if "users" in existing_tables:
        op.drop_table("users")
