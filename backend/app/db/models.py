"""Relational model (see docs/database.md for cardinality, deletion behaviour and index rationale).

JSON columns hold data that is always read and written as one unit with its parent (the normalised
document, evidence references, assessments). Anything that is queried, joined or changes independently
is a table.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user','admin')", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="user")
    created_at: Mapped[datetime] = _created()


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user", "user_id"), Index("ix_sessions_expires", "expires_at"))

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class ResumeDocument(Base):
    """A logical résumé; content lives in immutable ResumeVersion rows."""

    __tablename__ = "resume_documents"
    __table_args__ = (Index("ix_resume_documents_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created()
    versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="ResumeVersion.version_no"
    )


class ResumeVersion(Base):
    """Immutable once `ready` or `failed`: edits create the next version (documents.service)."""

    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_resume_versions_doc_no"),
        CheckConstraint("status IN ('processing','ready','failed')", name="ck_resume_versions_status"),
        CheckConstraint(
            "source IN ('upload','user_correction')", name="ck_resume_versions_source"
        ),
        Index("ix_resume_versions_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = _user_fk()  # denormalised: every ownership check is one predicate
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(64))
    original_ext: Mapped[str | None] = mapped_column(String(8))
    sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    normalized: Mapped[dict | None] = mapped_column(JSONB)
    parseability: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
    document: Mapped[ResumeDocument] = relationship(back_populates="versions")


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (Index("ix_job_descriptions_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created()
    versions: Mapped[list["JobDescriptionVersion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobDescriptionVersion.version_no"
    )


class JobDescriptionVersion(Base):
    __tablename__ = "job_description_versions"
    __table_args__ = (
        UniqueConstraint("job_id", "version_no", name="uq_jd_versions_job_no"),
        CheckConstraint("source IN ('paste','user_correction')", name="ck_jd_versions_source"),
        Index("ix_jd_versions_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = _user_fk()
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    job: Mapped[JobDescription] = relationship(back_populates="versions")
    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="jd_version", cascade="all, delete-orphan", order_by="JobRequirement.ordinal"
    )


class JobRequirement(Base):
    """A table because matches and user corrections both address a single requirement."""

    __tablename__ = "job_requirements"
    __table_args__ = (
        UniqueConstraint("jd_version_id", "ordinal", name="uq_job_requirements_ordinal"),
        CheckConstraint("kind IN ('required','preferred')", name="ck_job_requirements_kind"),
        CheckConstraint("origin IN ('extracted','inferred','user')", name="ck_job_requirements_origin"),
        CheckConstraint(
            "category IN ('skill','experience_years','education','certification','responsibility','soft_skill')",
            name="ck_job_requirements_category",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    jd_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_description_versions.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text_: Mapped[str] = mapped_column("text", Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    origin: Mapped[str] = mapped_column(String(12), nullable=False)
    terms: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    min_years: Mapped[float | None] = mapped_column(Float)
    source_span: Mapped[dict | None] = mapped_column(JSONB)
    jd_version: Mapped[JobDescriptionVersion] = relationship(back_populates="requirements")


class AnalysisRun(Base):
    """One résumé version analysed against one job-description version.

    Results (assessments, matches) and `status = 'succeeded'` are written in one transaction; the CHECK
    below makes a "succeeded" run without results impossible.
    """

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="ck_analysis_runs_status"
        ),
        CheckConstraint("(status = 'succeeded') = (assessments IS NOT NULL)", name="ck_analysis_runs_results"),
        Index("ix_analysis_runs_user_created", "user_id", "created_at"),
        Index("ix_analysis_runs_resume_version", "resume_version_id"),
        Index("ix_analysis_runs_jd_version", "jd_version_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False
    )
    jd_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_description_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_fingerprint: Mapped[str | None] = mapped_column(String(64))
    engine: Mapped[dict | None] = mapped_column(JSONB)  # mode, models, calibration, notes
    extraction: Mapped[list | None] = mapped_column(JSONB)  # mentions found in the résumé
    assessments: Mapped[list | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    warnings: Mapped[list | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matches: Mapped[list["RequirementMatch"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RequirementMatch(Base):
    __tablename__ = "requirement_matches"
    __table_args__ = (
        UniqueConstraint("run_id", "requirement_id", name="uq_matches_run_requirement"),
        CheckConstraint(
            "status IN ('supported','mentioned_only','contradicted','insufficient','no_evidence')",
            name="ck_matches_status",
        ),
        CheckConstraint("probability IS NULL OR (probability >= 0 AND probability <= 1)", name="ck_matches_probability"),
        Index("ix_matches_requirement", "requirement_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_requirements.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    probability: Mapped[float | None] = mapped_column(Float)  # calibrated only; NULL means "no calibrated estimate"
    conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    run: Mapped[AnalysisRun] = relationship(back_populates="matches")


class ProcessingJob(Base):
    """Database-backed queue. See jobs/queue.py for the lifecycle and locking rules."""

    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('extract_resume','run_analysis')", name="ck_jobs_kind"),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_jobs_status"),
        CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts"),
        UniqueConstraint("kind", "target_id", name="uq_jobs_kind_target"),
        Index("ix_jobs_claimable", "next_run_at", postgresql_where=text("status IN ('queued','running')")),
        Index("ix_jobs_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IdempotencyKey(Base):
    """The single idempotency mechanism: claiming a key is an INSERT ... ON CONFLICT DO NOTHING."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", "key", name="uq_idempotency"),
        Index("ix_idempotency_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class AuditEvent(Base):
    """Survives user deletion (user_id becomes NULL). Never stores document content."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_created", "created_at"), Index("ix_audit_user", "user_id"))

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
