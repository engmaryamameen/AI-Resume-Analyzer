"""Registers the two job kinds. Imported by the worker; the API never executes jobs."""

import uuid

from sqlalchemy.orm import Session

from app.analysis import service as analysis
from app.db.models import ResumeVersion
from app.documents import service as documents
from app.jobs.registry import JobKind, register


def _cancel_extraction(db: Session, version_id: uuid.UUID) -> None:
    version = db.get(ResumeVersion, version_id)
    if version is not None and version.status == "processing":
        version.status, version.error_code = "failed", "cancelled"


register(JobKind(
    name="extract_resume", prepare=documents.prepare_extraction, compute=documents.compute_extraction,
    commit=documents.commit_extraction, on_failed=documents.fail_extraction, on_cancelled=_cancel_extraction))

register(JobKind(
    name="run_analysis", prepare=analysis.prepare_analysis, compute=analysis.compute_analysis,
    commit=analysis.commit_analysis, on_failed=analysis.mark_analysis_failed,
    on_cancelled=analysis.mark_analysis_cancelled))
