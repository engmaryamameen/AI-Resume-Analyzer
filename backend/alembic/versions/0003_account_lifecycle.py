"""Single-use account lifecycle tokens and verified email ownership."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_table(
        "account_tokens",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('verify_email','reset_password')", name="ck_account_token_purpose"),
    )
    op.create_index("ix_account_tokens_user_purpose", "account_tokens", ["user_id", "purpose"])
    op.create_index("ix_account_tokens_expires", "account_tokens", ["expires_at"])


def downgrade():
    op.drop_table("account_tokens")
    op.drop_column("users", "email_verified_at")
