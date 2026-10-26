"""Administrative operations. Scope is intentionally narrow: aggregate health and maintenance.

Administrators cannot read résumé content, job descriptions, analyses or user email addresses through
any endpoint here, and every admin action is written to the audit log. The role is granted only through
`python -m app.cli grant-admin`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_request_id, get_store
from app.auth.deps import require_admin
from app.core.config import Settings, get_settings
from app.db.models import AnalysisRun, AuditEvent, ProcessingJob, ResumeDocument, ResumeVersion, User
from app.db.session import get_db
from app.documents.storage import BlobStore
from app.jobs import queue
from app.maintenance import run_maintenance

router = APIRouter(prefix="/admin", tags=["admin"])


def _counts(db: Session, column) -> dict[str, int]:  # noqa: ANN001
    return dict(db.execute(select(column, func.count()).group_by(column)).all())


@router.get("/overview")
def overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    db.add(AuditEvent(user_id=admin.id, action="admin.overview_viewed", request_id=current_request_id()))
    db.commit()
    queue.refresh_depth_gauge(db)
    return {
        "users": db.execute(select(func.count()).select_from(User)).scalar_one(),
        "resumes": db.execute(select(func.count()).select_from(ResumeDocument)).scalar_one(),
        "resume_versions_by_status": _counts(db, ResumeVersion.status),
        "analyses_by_status": _counts(db, AnalysisRun.status),
        "jobs_by_status": _counts(db, ProcessingJob.status),
    }


@router.post("/maintenance")
def maintenance(
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
    store: BlobStore = Depends(get_store), settings: Settings = Depends(get_settings),
) -> dict:
    result = run_maintenance(db, store, settings)
    db.add(AuditEvent(user_id=admin.id, action="admin.maintenance", request_id=current_request_id(), detail=result))
    db.commit()
    return result
