import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import service
from app.analysis.schema import AnalysisWarning, Assessment, EvidenceRef, Recommendation
from app.api.schemas import AnalysisCreateIn, AnalysisDetailOut, AnalysisOut, MatchOut, Page, RequirementOut, Staleness
from app.auth.deps import current_user
from app.core.config import Settings, get_settings
from app.core.errors import Conflict
from app.core.ratelimit import limiter
from app.db.models import (
    AnalysisRun,
    JobDescriptionVersion,
    JobRequirement,
    RequirementMatch,
    ResumeVersion,
    User,
)
from app.db.session import get_db
from app.history.comparison import compare_runs
from app.ml.contracts import EngineInfo, Mention
from app.ml.manifest import current_fingerprint
from app.reports import builder

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _out(db: Session, run: AnalysisRun, settings: Settings) -> dict:
    resume = db.get(ResumeVersion, run.resume_version_id)
    job = db.get(JobDescriptionVersion, run.jd_version_id)
    latest_resume = db.execute(
        select(ResumeVersion.id).where(ResumeVersion.document_id == resume.document_id)
        .order_by(ResumeVersion.version_no.desc()).limit(1)).scalar_one_or_none() if resume else None
    latest_job = db.execute(
        select(JobDescriptionVersion.id).where(JobDescriptionVersion.job_id == job.job_id)
        .order_by(JobDescriptionVersion.version_no.desc()).limit(1)).scalar_one_or_none() if job else None
    return {
        "id": run.id, "status": run.status, "resume_version_id": run.resume_version_id,
        "resume_document_id": resume.document_id if resume else None,
        "resume_version_no": resume.version_no if resume else None, "jd_version_id": run.jd_version_id,
        "latest_resume_version_id": latest_resume, "latest_jd_version_id": latest_job,
        "pipeline_version": run.pipeline_version,
        "engine": EngineInfo.model_validate(run.engine) if run.engine else None,
        "error_code": run.error_code, "created_at": run.created_at, "completed_at": run.completed_at,
        "staleness": Staleness(**service.staleness(db, run, current_fingerprint(settings.model_dir))),
    }


def _requirement_out(r: JobRequirement) -> RequirementOut:
    return RequirementOut(id=r.id, ordinal=r.ordinal, text=r.text_, kind=r.kind, category=r.category,
                          origin=r.origin, terms=list(r.terms), min_years=r.min_years, source_span=r.source_span)


def _load_matches(db: Session, run: AnalysisRun) -> list[tuple[RequirementMatch, JobRequirement]]:
    rows = db.execute(
        select(RequirementMatch, JobRequirement)
        .join(JobRequirement, JobRequirement.id == RequirementMatch.requirement_id)
        .where(RequirementMatch.run_id == run.id).order_by(JobRequirement.ordinal)
    ).all()
    return [(m, r) for m, r in rows]


@router.post("", response_model=AnalysisOut, status_code=202)
def create_analysis(
    body: AnalysisCreateIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> dict:
    """Queues an analysis of one résumé version against one job-description version. Repeating the
    request with the same Idempotency-Key returns the same analysis instead of creating another."""
    limiter.check(f"analysis:{user.id}", settings.rate_limit_upload_per_minute)
    run = service.create_analysis(db, settings, user.id, body.resume_version_id, body.jd_version_id, idempotency_key)
    return _out(db, run, settings)


@router.get("", response_model=Page[AnalysisOut])
def list_analyses(
    limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10_000),
    user: User = Depends(current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> Page[AnalysisOut]:
    total = db.execute(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.user_id == user.id)).scalar_one()
    runs = db.execute(select(AnalysisRun).where(AnalysisRun.user_id == user.id)
                      .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id).limit(limit).offset(offset)).scalars().all()
    return Page(items=[AnalysisOut(**_out(db, r, settings)) for r in runs], total=total, limit=limit, offset=offset)


@router.get("/compare")
def compare(
    base: uuid.UUID, target: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    return compare_runs(db, user.id, base, target)


@router.get("/{analysis_id}", response_model=AnalysisDetailOut)
def get_analysis(
    analysis_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalysisDetailOut:
    run = service.get_run(db, user.id, analysis_id)
    matches = [
        MatchOut(requirement=_requirement_out(r), status=m.status, conflict=m.conflict, probability=m.probability,  # type: ignore[arg-type]
                 reasons=list(m.reasons), evidence=[EvidenceRef.model_validate(e) for e in m.evidence],
                 explanation=m.explanation)
        for m, r in _load_matches(db, run)]
    summary = run.summary or {}
    return AnalysisDetailOut(
        **_out(db, run, settings),
        assessments=[Assessment.model_validate(a) for a in run.assessments] if run.assessments else None,
        warnings=[AnalysisWarning.model_validate(w) for w in run.warnings or []],
        recommendations=[Recommendation.model_validate(r) for r in summary.get("recommendations", [])],
        limitations=list(summary.get("limitations", [])), matches=matches,
        mentions=[Mention.model_validate(m) for m in run.extraction or []])


@router.post("/{analysis_id}/cancel", response_model=AnalysisOut)
def cancel(
    analysis_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    return _out(db, service.cancel_analysis(db, user.id, analysis_id), settings)


@router.get("/{analysis_id}/report")
def report(
    analysis_id: uuid.UUID, format: Literal["json", "md", "csv"] = "json",
    user: User = Depends(current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> Response:
    run = service.get_run(db, user.id, analysis_id)
    if run.status != "succeeded":
        raise Conflict("The analysis has not completed.", code="analysis_not_complete")
    stale = service.staleness(db, run, current_fingerprint(settings.model_dir))
    pairs = _load_matches(db, run)
    data = builder.build_report(
        run=run, staleness=stale,
        requirements=[{"id": r.id, "text": r.text_, "kind": r.kind, "category": r.category, "origin": r.origin}
                      for _, r in pairs],
        matches=[{"requirement_id": m.requirement_id, "status": m.status, "probability": m.probability,
                  "conflict": m.conflict, "reasons": m.reasons, "evidence": m.evidence,
                  "explanation": m.explanation} for m, _ in pairs])
    body, media, extension = {
        "json": (builder.to_json(data), "application/json", "json"),
        "md": (builder.to_markdown(data), "text/markdown; charset=utf-8", "md"),
        "csv": (builder.to_csv(data), "text/csv; charset=utf-8", "csv"),
    }[format]
    return Response(body, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="analysis-{run.id}.{extension}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})
