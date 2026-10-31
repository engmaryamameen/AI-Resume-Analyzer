"""Job description versions and user-corrected requirements."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.requirements import certification_terms, education_markers, extract_requirements
from app.analysis.schema import (
    AnalysisWarning,
    RequirementCategory,
    RequirementDraft,
    RequirementKind,
)
from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.core.textclean import strip_controls
from app.db.models import JobDescription, JobDescriptionVersion, JobRequirement
from app.db.versioning import lock_and_check_latest
from app.lang.taxonomy import get_taxonomy

MAX_REQUIREMENTS_PER_VERSION = 80


class RequirementInput(BaseModel):
    id: uuid.UUID | None = None  # present = an existing requirement, possibly edited
    text: str = Field(min_length=2, max_length=500)
    kind: RequirementKind
    category: RequirementCategory = "responsibility"
    min_years: float | None = Field(default=None, ge=0, le=60)


def clean_text(raw: str, settings: Settings) -> str:
    text = strip_controls(raw.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if len(text) < 40:
        raise ValidationFailed("The job description is too short to analyse.", code="jd_too_short")
    if len(text) > settings.max_jd_chars:
        raise ValidationFailed(
            f"The job description exceeds {settings.max_jd_chars} characters.", code="jd_too_long"
        )
    return text


def _rows(version_id: uuid.UUID, drafts: list[RequirementDraft]) -> list[JobRequirement]:
    return [
        JobRequirement(
            jd_version_id=version_id,
            ordinal=d.ordinal,
            text_=d.text,
            kind=d.kind,
            category=d.category,
            origin=d.origin,
            terms=d.terms,
            min_years=d.min_years,
            source_span=d.source_span,
        )
        for d in drafts
    ]


def create_job(
    db: Session, settings: Settings, user_id: uuid.UUID, title: str, raw_text: str
) -> tuple[JobDescription, JobDescriptionVersion, list[AnalysisWarning]]:
    text = clean_text(raw_text, settings)
    drafts, warnings = extract_requirements(text)
    job = JobDescription(user_id=user_id, title=title.strip()[:200] or "Untitled role")
    db.add(job)
    db.flush()
    version = JobDescriptionVersion(
        job_id=job.id, user_id=user_id, version_no=1, source="paste", raw_text=text
    )
    db.add(version)
    db.flush()
    db.add_all(_rows(version.id, drafts))
    db.commit()
    return job, version, warnings


def get_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDescription:
    job = db.execute(
        select(JobDescription).where(JobDescription.id == job_id, JobDescription.user_id == user_id)
    ).scalar_one_or_none()
    if job is None:
        raise NotFound("Job description not found.")
    return job


def get_version(
    db: Session, user_id: uuid.UUID, job_id: uuid.UUID, version_no: int | None = None
) -> JobDescriptionVersion:
    query = select(JobDescriptionVersion).where(
        JobDescriptionVersion.job_id == job_id, JobDescriptionVersion.user_id == user_id
    )
    query = (
        query.where(JobDescriptionVersion.version_no == version_no)
        if version_no
        else query.order_by(JobDescriptionVersion.version_no.desc()).limit(1)
    )
    version = db.execute(query).scalar_one_or_none()
    if version is None:
        raise NotFound("Job description version not found.")
    return version


def get_version_by_id(
    db: Session, user_id: uuid.UUID, version_id: uuid.UUID
) -> JobDescriptionVersion:
    version = db.execute(
        select(JobDescriptionVersion).where(
            JobDescriptionVersion.id == version_id, JobDescriptionVersion.user_id == user_id
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("Job description version not found.")
    return version


def latest_version_no(db: Session, job_id: uuid.UUID) -> int:
    return db.execute(
        select(func.coalesce(func.max(JobDescriptionVersion.version_no), 0)).where(
            JobDescriptionVersion.job_id == job_id
        )
    ).scalar_one()


def _terms_for(category: str, text: str) -> list[str]:
    """The same term derivation the extractor uses, so editing a requirement can't lose its markers."""
    if category in {"skill", "soft_skill"}:
        return get_taxonomy().ids_in(text)[:1]  # a skill requirement addresses exactly one term
    if category == "education":
        return education_markers(text)
    if category == "certification":
        return certification_terms(text)
    return get_taxonomy().ids_in(text)[
        :6
    ]  # responsibilities and years requirements may name skills


def replace_requirements(
    db: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    base_version_no: int,
    items: list[RequirementInput],
) -> JobDescriptionVersion:
    """User corrections create a new immutable version; earlier analyses keep the version they used."""
    if len(items) > MAX_REQUIREMENTS_PER_VERSION:
        raise ValidationFailed("Too many requirements.", code="too_many_requirements")
    get_job(db, user_id, job_id)
    current = lock_and_check_latest(
        db, JobDescription, job_id, lambda: latest_version_no(db, job_id), base_version_no
    )
    base = get_version(db, user_id, job_id, current)
    existing = {r.id: r for r in base.requirements}

    version = JobDescriptionVersion(
        job_id=job_id,
        user_id=user_id,
        version_no=current + 1,
        source="user_correction",
        raw_text=base.raw_text,
    )
    db.add(version)
    db.flush()

    rows: list[JobRequirement] = []
    for ordinal, item in enumerate(items):
        prior = existing.get(item.id) if item.id else None
        if item.id and prior is None:
            raise ValidationFailed(
                "A requirement does not belong to this job description.", code="unknown_requirement"
            )
        unchanged = (
            prior is not None and prior.text_ == item.text and prior.category == item.category
        )
        text = item.text.strip()
        terms = list(prior.terms) if unchanged and prior else _terms_for(item.category, text)
        category = item.category
        if category in {"skill", "soft_skill"} and not terms:
            category = "responsibility"
            terms = _terms_for(category, text)
        rows.append(
            JobRequirement(
                jd_version_id=version.id,
                ordinal=ordinal,
                text_=text,
                kind=item.kind,
                category=category,
                origin=prior.origin if unchanged and prior else "user",
                terms=terms,
                min_years=item.min_years
                if item.min_years is not None
                else (prior.min_years if prior else None),
                source_span=prior.source_span if unchanged and prior else None,
            )
        )
    db.add_all(rows)
    db.commit()
    return version
