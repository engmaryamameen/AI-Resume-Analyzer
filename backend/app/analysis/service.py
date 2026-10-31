"""Analysis lifecycle: create (idempotent), process (as a job), cancel, staleness."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.job_descriptions import get_version_by_id as get_jd_version_by_id
from app.analysis.pipeline import analyze
from app.analysis.schema import AnalysisResult, RequirementDraft
from app.core.config import PIPELINE_VERSION, Settings, get_settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.metrics import ANALYSIS_ENGINE, ANALYSIS_RESULTS, ANALYSIS_SECONDS
from app.db import idempotency
from app.db.locks import lock_user
from app.db.models import AnalysisRun, JobDescriptionVersion, RequirementMatch, ResumeVersion
from app.documents.schema import NormalizedDocument, Parseability
from app.documents.service import get_version_by_id as get_resume_version_by_id
from app.jobs import queue
from app.jobs.registry import JobContext
from app.ml.engine import Budget

_ACTIVE = ("queued", "running")


def create_analysis(
    db: Session,
    settings: Settings,
    user_id: uuid.UUID,
    resume_version_id: uuid.UUID,
    jd_version_id: uuid.UUID,
    idempotency_key: str | None,
) -> AnalysisRun:
    resume = get_resume_version_by_id(db, user_id, resume_version_id)
    job = get_jd_version_by_id(db, user_id, jd_version_id)
    if resume.status != "ready":
        raise Conflict("The résumé has not been read successfully yet.", code="version_not_ready")

    run_id = uuid.uuid4()
    key = idempotency.validate_key(idempotency_key)
    if key:
        digest = hashlib.sha256(f"{resume.id}:{job.id}".encode()).hexdigest()
        existing = idempotency.claim(db, user_id, "analysis", key, digest, run_id)
        if existing is not None:
            db.rollback()
            return get_run(db, user_id, existing)

    run = AnalysisRun(
        id=run_id,
        user_id=user_id,
        resume_version_id=resume.id,
        jd_version_id=job.id,
        status="queued",
        pipeline_version=PIPELINE_VERSION,
    )
    db.add(run)
    db.flush()
    queue.enqueue(
        db,
        user_id=user_id,
        kind="run_analysis",
        target_id=run.id,
        max_attempts=settings.job_max_attempts,
    )
    db.commit()
    return run


def get_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> AnalysisRun:
    run = db.execute(
        select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.user_id == user_id)
    ).scalar_one_or_none()
    if run is None:
        raise NotFound("Analysis not found.")
    return run


# ---- job handlers (registered in app.jobs.handlers) -------------------------------------------------


@dataclass(frozen=True)
class AnalysisWork:
    document: NormalizedDocument
    parseability: Parseability
    requirements: list[RequirementDraft]
    requirement_ids: dict[int, uuid.UUID]


@dataclass(frozen=True)
class AnalysisOutcome:
    result: AnalysisResult
    requirement_ids: dict[int, uuid.UUID]
    seconds: float


def prepare_analysis(db: Session, run_id: uuid.UUID) -> AnalysisWork | None:
    run = db.get(AnalysisRun, run_id)
    if run is None or run.status not in _ACTIVE:
        return None
    resume = db.get(ResumeVersion, run.resume_version_id)
    job = db.get(JobDescriptionVersion, run.jd_version_id)
    if resume is None or job is None or resume.normalized is None or resume.parseability is None:
        raise ValidationFailed(
            "The inputs of this analysis are no longer available.", code="inputs_unavailable"
        )
    run.status = "running"
    rows = list(job.requirements)
    return AnalysisWork(
        document=NormalizedDocument.model_validate(resume.normalized),
        parseability=Parseability.model_validate(resume.parseability),
        requirements=[
            RequirementDraft(
                ordinal=r.ordinal,
                text=r.text_,
                kind=r.kind,
                category=r.category,
                origin=r.origin,
                terms=list(r.terms),
                min_years=r.min_years,
                source_span=r.source_span,
            )
            for r in rows
        ],
        requirement_ids={r.ordinal: r.id for r in rows},
    )


def compute_analysis(work: AnalysisWork, ctx: JobContext) -> AnalysisOutcome:
    settings = get_settings()
    started = datetime.now(UTC)
    result = analyze(
        work.document,
        work.parseability,
        work.requirements,
        ctx.engine,
        lambda: Budget(settings.ml_max_seconds, ctx.heartbeat),
    )
    return AnalysisOutcome(
        result, work.requirement_ids, (datetime.now(UTC) - started).total_seconds()
    )


def commit_analysis(db: Session, run_id: uuid.UUID, outcome: AnalysisOutcome) -> None:
    run = db.execute(
        select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update()
    ).scalar_one_or_none()
    if run is None or run.status not in _ACTIVE:
        return
    result = outcome.result
    for match in result.matches:
        db.add(
            RequirementMatch(
                run_id=run.id,
                requirement_id=outcome.requirement_ids[match.ordinal],
                status=match.status,
                probability=match.probability,
                conflict=match.conflict,
                reasons=match.reasons,
                evidence=[e.model_dump(mode="json") for e in match.evidence],
                explanation=match.explanation,
            )
        )
    run.assessments = [a.model_dump(mode="json") for a in result.assessments]
    run.summary = {
        "recommendations": [r.model_dump(mode="json") for r in result.recommendations],
        "limitations": result.limitations,
    }
    run.warnings = [w.model_dump(mode="json") for w in result.warnings]
    run.engine = result.engine.model_dump(mode="json")
    run.extraction = [m.model_dump(mode="json") for m in result.mentions]
    run.model_fingerprint = result.engine.fingerprint
    run.pipeline_version = result.pipeline_version
    run.status, run.error_code, run.completed_at = "succeeded", None, datetime.now(UTC)
    ANALYSIS_RESULTS.labels(outcome="succeeded").inc()
    ANALYSIS_ENGINE.labels(mode=result.engine.mode).inc()
    ANALYSIS_SECONDS.observe(outcome.seconds)


def mark_analysis_failed(db: Session, run_id: uuid.UUID, code: str) -> None:
    run = db.get(AnalysisRun, run_id)
    if run is not None and run.status in _ACTIVE:
        run.status, run.error_code, run.completed_at = "failed", code[:64], datetime.now(UTC)
        ANALYSIS_RESULTS.labels(outcome="failed").inc()


def mark_analysis_cancelled(db: Session, run_id: uuid.UUID) -> None:
    run = db.get(AnalysisRun, run_id)
    if run is not None and run.status in _ACTIVE:
        run.status, run.completed_at = "cancelled", datetime.now(UTC)
        ANALYSIS_RESULTS.labels(outcome="cancelled").inc()


# ---- API operations ---------------------------------------------------------------------------------


def cancel_analysis(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> AnalysisRun:
    """Queued runs are cancelled at once; a running one is flagged and its worker discards its result."""
    lock_user(db, user_id)
    run = get_run(db, user_id, run_id)
    if run.status in _ACTIVE:
        if queue.cancel_for_target(db, user_id, "run_analysis", run_id) in {None, "cancelled"}:
            mark_analysis_cancelled(db, run_id)
    db.commit()
    db.refresh(run)
    return run


def staleness(db: Session, run: AnalysisRun, current_fingerprint: str) -> dict[str, Any]:
    """A result is current only if it used the latest versions and the models that would be used today."""
    reasons: list[str] = []
    resume = db.get(ResumeVersion, run.resume_version_id)
    job = db.get(JobDescriptionVersion, run.jd_version_id)
    if resume is not None:
        latest = db.execute(
            select(ResumeVersion.version_no)
            .where(ResumeVersion.document_id == resume.document_id)
            .order_by(ResumeVersion.version_no.desc())
            .limit(1)
        ).scalar_one()
        if latest != resume.version_no:
            reasons.append("resume_version_superseded")
    if job is not None:
        latest = db.execute(
            select(JobDescriptionVersion.version_no)
            .where(JobDescriptionVersion.job_id == job.job_id)
            .order_by(JobDescriptionVersion.version_no.desc())
            .limit(1)
        ).scalar_one()
        if latest != job.version_no:
            reasons.append("job_description_version_superseded")
    if run.status == "succeeded" and (
        run.pipeline_version != PIPELINE_VERSION or run.model_fingerprint != current_fingerprint
    ):
        reasons.append("analysis_method_changed")
    return {"is_stale": bool(reasons), "reasons": reasons}
