"""Durable guest allowance and expiring private analysis workspaces."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_allowances",
        sa.Column("network_key", sa.String(64), primary_key=True),
        sa.Column("next_allowed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "guest_analyses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("network_key", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "resume_version_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("resume_versions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "jd_version_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("job_description_versions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guest_expires", "guest_analyses", ["expires_at"])
    op.create_index("ix_guest_network", "guest_analyses", ["network_key"])


def downgrade() -> None:
    op.drop_table("guest_analyses")
    op.drop_table("guest_allowances")
