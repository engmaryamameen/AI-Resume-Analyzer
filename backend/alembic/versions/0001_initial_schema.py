"""Initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = pg.UUID(as_uuid=True)
NOW = sa.text("now()")


def _pk() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False)


def _user_fk() -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        _pk(),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        _created(),
        sa.CheckConstraint("role IN ('user','admin')", name="ck_users_role"),
    )

    op.create_table(
        "sessions",
        _pk(),
        _user_fk(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _created(),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires", "sessions", ["expires_at"])

    op.create_table(
        "resume_documents",
        _pk(),
        _user_fk(),
        sa.Column("title", sa.String(200), nullable=False),
        _created(),
    )
    op.create_index("ix_resume_documents_user_created", "resume_documents", ["user_id", "created_at"])

    op.create_table(
        "resume_versions",
        _pk(),
        sa.Column("document_id", UUID, sa.ForeignKey("resume_documents.id", ondelete="CASCADE"), nullable=False),
        _user_fk(),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("storage_key", sa.String(64)),
        sa.Column("original_ext", sa.String(8)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("normalized", pg.JSONB),
        sa.Column("parseability", pg.JSONB),
        _created(),
        sa.UniqueConstraint("document_id", "version_no", name="uq_resume_versions_doc_no"),
        sa.CheckConstraint("status IN ('processing','ready','failed')", name="ck_resume_versions_status"),
        sa.CheckConstraint("source IN ('upload','user_correction')", name="ck_resume_versions_source"),
    )
    op.create_index("ix_resume_versions_user", "resume_versions", ["user_id"])

    op.create_table(
        "job_descriptions",
        _pk(),
        _user_fk(),
        sa.Column("title", sa.String(200), nullable=False),
        _created(),
    )
    op.create_index("ix_job_descriptions_user_created", "job_descriptions", ["user_id", "created_at"])

    op.create_table(
        "job_description_versions",
        _pk(),
        sa.Column("job_id", UUID, sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False),
        _user_fk(),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        _created(),
        sa.UniqueConstraint("job_id", "version_no", name="uq_jd_versions_job_no"),
        sa.CheckConstraint("source IN ('paste','user_correction')", name="ck_jd_versions_source"),
    )
    op.create_index("ix_jd_versions_user", "job_description_versions", ["user_id"])

    op.create_table(
        "job_requirements",
        _pk(),
        sa.Column(
            "jd_version_id", UUID, sa.ForeignKey("job_description_versions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(12), nullable=False),
        sa.Column("terms", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("min_years", sa.Float),
        sa.Column("source_span", pg.JSONB),
        sa.UniqueConstraint("jd_version_id", "ordinal", name="uq_job_requirements_ordinal"),
        sa.CheckConstraint("kind IN ('required','preferred')", name="ck_job_requirements_kind"),
        sa.CheckConstraint("origin IN ('extracted','inferred','user')", name="ck_job_requirements_origin"),
        sa.CheckConstraint(
            "category IN ('skill','experience_years','education','certification','responsibility','soft_skill')",
            name="ck_job_requirements_category",
        ),
    )

    op.create_table(
        "analysis_runs",
        _pk(),
        _user_fk(),
        sa.Column("resume_version_id", UUID, sa.ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "jd_version_id", UUID, sa.ForeignKey("job_description_versions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("pipeline_version", sa.String(32), nullable=False),
        sa.Column("model_fingerprint", sa.String(64)),
        sa.Column("engine", pg.JSONB),
        sa.Column("extraction", pg.JSONB),
        sa.Column("assessments", pg.JSONB),
        sa.Column("summary", pg.JSONB),
        sa.Column("warnings", pg.JSONB),
        sa.Column("error_code", sa.String(64)),
        _created(),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="ck_analysis_runs_status"
        ),
        sa.CheckConstraint("(status = 'succeeded') = (assessments IS NOT NULL)", name="ck_analysis_runs_results"),
    )
    op.create_index("ix_analysis_runs_user_created", "analysis_runs", ["user_id", "created_at"])
    op.create_index("ix_analysis_runs_resume_version", "analysis_runs", ["resume_version_id"])
    op.create_index("ix_analysis_runs_jd_version", "analysis_runs", ["jd_version_id"])

    op.create_table(
        "requirement_matches",
        _pk(),
        sa.Column("run_id", UUID, sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", UUID, sa.ForeignKey("job_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("probability", sa.Float),
        sa.Column("conflict", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("reasons", pg.JSONB, nullable=False),
        sa.Column("evidence", pg.JSONB, nullable=False),
        sa.Column("explanation", sa.Text),
        sa.UniqueConstraint("run_id", "requirement_id", name="uq_matches_run_requirement"),
        sa.CheckConstraint(
            "status IN ('supported','mentioned_only','contradicted','insufficient','no_evidence')",
            name="ck_matches_status",
        ),
        sa.CheckConstraint("probability IS NULL OR (probability >= 0 AND probability <= 1)", name="ck_matches_probability"),
    )
    op.create_index("ix_matches_requirement", "requirement_matches", ["requirement_id"])

    op.create_table(
        "processing_jobs",
        _pk(),
        _user_fk(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_error_code", sa.String(64)),
        _created(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.UniqueConstraint("kind", "target_id", name="uq_jobs_kind_target"),
        sa.CheckConstraint("kind IN ('extract_resume','run_analysis')", name="ck_jobs_kind"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_jobs_status"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts"),
    )
    op.create_index(
        "ix_jobs_claimable", "processing_jobs", ["next_run_at"], postgresql_where=sa.text("status IN ('queued','running')")
    )
    op.create_index("ix_jobs_user", "processing_jobs", ["user_id"])

    op.create_table(
        "idempotency_keys",
        _pk(),
        _user_fk(),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_id", UUID, nullable=False),
        _created(),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_idempotency"),
    )
    op.create_index("ix_idempotency_created", "idempotency_keys", ["created_at"])

    op.create_table(
        "audit_events",
        _pk(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("detail", pg.JSONB),
        _created(),
    )
    op.create_index("ix_audit_created", "audit_events", ["created_at"])
    op.create_index("ix_audit_user", "audit_events", ["user_id"])


def downgrade() -> None:
    for table in (
        "audit_events",
        "idempotency_keys",
        "processing_jobs",
        "requirement_matches",
        "analysis_runs",
        "job_requirements",
        "job_description_versions",
        "job_descriptions",
        "resume_versions",
        "resume_documents",
        "sessions",
        "users",
    ):
        op.drop_table(table)
