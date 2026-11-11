"""Allow a résumé review without manufacturing a target role."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("analysis_runs", "jd_version_id", existing_type=pg.UUID(), nullable=True)


def downgrade():
    # Refuse to destroy résumé-only history to satisfy an older schema.
    if op.get_bind().execute(sa.text("SELECT 1 FROM analysis_runs WHERE jd_version_id IS NULL LIMIT 1")).first():
        raise RuntimeError("Resume-only analyses exist; export or migrate them before downgrading")
    op.alter_column("analysis_runs", "jd_version_id", existing_type=pg.UUID(), nullable=False)
