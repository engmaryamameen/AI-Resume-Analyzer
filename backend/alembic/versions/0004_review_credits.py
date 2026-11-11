"""Optional Stripe test orders and review-credit accounting."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("billing_orders",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), unique=True),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "request_key", name="uq_billing_request"))
    op.create_table("credit_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("reference_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "kind", "reference_id", name="uq_credit_reference"),
        sa.CheckConstraint("(kind = 'purchase' AND amount = 5) OR (kind = 'review' AND amount = -1) OR (kind = 'refund' AND amount = 1)", name="ck_credit_amount"))


def downgrade():
    op.drop_table("credit_entries")
    op.drop_table("billing_orders")
