import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import job_descriptions as jd
from app.analysis.requirements import extract_requirements
from app.api.deps import current_request_id
from app.api.schemas import (
    JobCreateIn,
    JobDetailOut,
    JobOut,
    JobVersionOut,
    Page,
    RequirementOut,
    RequirementsReplaceIn,
)
from app.auth.deps import current_user
from app.core.config import Settings, get_settings
from app.db.models import JobDescription, JobDescriptionVersion, User
from app.db.session import get_db
from app.privacy import deletion

router = APIRouter(prefix="/job-descriptions", tags=["job descriptions"])


def _version_out(v: JobDescriptionVersion) -> JobVersionOut:
    return JobVersionOut(id=v.id, version_no=v.version_no, source=v.source, created_at=v.created_at)


def _job_out(job: JobDescription, latest: JobDescriptionVersion) -> JobOut:
    return JobOut(id=job.id, title=job.title, created_at=job.created_at, latest_version=_version_out(latest))


def _detail(job: JobDescription, versions: list[JobDescriptionVersion], chosen: JobDescriptionVersion,
            warnings: list) -> JobDetailOut:
    base = _job_out(job, versions[-1])
    reqs = [RequirementOut(id=r.id, ordinal=r.ordinal, text=r.text_, kind=r.kind, category=r.category,
                           origin=r.origin, terms=list(r.terms), min_years=r.min_years, source_span=r.source_span)
            for r in chosen.requirements]
    return JobDetailOut(**base.model_dump(), raw_text=chosen.raw_text, requirements=reqs, warnings=warnings,
                        versions=[_version_out(v) for v in versions])


@router.post("", response_model=JobDetailOut, status_code=201)
def create_job(
    body: JobCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobDetailOut:
    job, version, warnings = jd.create_job(db, settings, user.id, body.title, body.text)
    return _detail(job, [version], version, warnings)


@router.get("", response_model=Page[JobOut])
def list_jobs(
    limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=10_000),
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> Page[JobOut]:
    total = db.execute(select(func.count()).select_from(JobDescription).where(
        JobDescription.user_id == user.id)).scalar_one()
    jobs = db.execute(select(JobDescription).where(JobDescription.user_id == user.id)
                      .order_by(JobDescription.created_at.desc(), JobDescription.id)
                      .limit(limit).offset(offset)).scalars().all()
    latest: dict[uuid.UUID, JobDescriptionVersion] = {}
    if jobs:
        for v in db.execute(select(JobDescriptionVersion).where(
                JobDescriptionVersion.job_id.in_([j.id for j in jobs]))
                .order_by(JobDescriptionVersion.version_no)).scalars():
            latest[v.job_id] = v
    return Page(items=[_job_out(j, latest[j.id]) for j in jobs], total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(
    job_id: uuid.UUID, version: int | None = Query(None, ge=1),
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> JobDetailOut:
    job = jd.get_job(db, user.id, job_id)
    chosen = jd.get_version(db, user.id, job_id, version)
    versions = db.execute(select(JobDescriptionVersion).where(JobDescriptionVersion.job_id == job_id)
                          .order_by(JobDescriptionVersion.version_no)).scalars().all()
    _, warnings = extract_requirements(chosen.raw_text) if chosen.source == "paste" else ([], [])
    return _detail(job, list(versions), chosen, warnings)


@router.put("/{job_id}/requirements", response_model=JobDetailOut)
def replace_requirements(
    job_id: uuid.UUID, body: RequirementsReplaceIn,
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> JobDetailOut:
    """Saves corrected requirements as a NEW version; earlier analyses keep the version they used."""
    jd.replace_requirements(db, user.id, job_id, body.base_version_no, body.requirements)
    job = jd.get_job(db, user.id, job_id)
    versions = db.execute(select(JobDescriptionVersion).where(JobDescriptionVersion.job_id == job_id)
                          .order_by(JobDescriptionVersion.version_no)).scalars().all()
    return _detail(job, list(versions), versions[-1], [])


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    deletion.delete_job_description(db, user.id, job_id, current_request_id())
    return Response(status_code=204)
