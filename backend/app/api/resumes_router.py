import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_request_id, get_store
from app.api.schemas import (
    CorrectionIn,
    Page,
    ResumeDetailOut,
    ResumeOut,
    ResumeVersionOut,
)
from app.auth.deps import current_user
from app.core.config import Settings, get_settings
from app.core.ratelimit import limiter
from app.db import idempotency
from app.db.models import ResumeDocument, ResumeVersion, User
from app.db.session import get_db
from app.documents import service
from app.documents.storage import BlobStore
from app.documents.validation import validate_upload
from app.privacy import deletion

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _version_out(v: ResumeVersion) -> ResumeVersionOut:
    return ResumeVersionOut(
        id=v.id,
        version_no=v.version_no,
        source=v.source,
        status=v.status,
        error_code=v.error_code,
        parseability=v.parseability,
        created_at=v.created_at,
    )


def _resume_out(doc: ResumeDocument, latest: ResumeVersion) -> ResumeOut:
    return ResumeOut(
        id=doc.id, title=doc.title, created_at=doc.created_at, latest_version=_version_out(latest)
    )


@router.post("", response_model=ResumeOut, status_code=202)
def upload_resume(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: BlobStore = Depends(get_store),
) -> ResumeOut:
    """Accepts a PDF or DOCX. Extraction runs asynchronously; poll the résumé until its version is
    `ready` or `failed`. Repeating the request with the same Idempotency-Key returns the same résumé."""
    limiter.check(f"upload:{user.id}", settings.rate_limit_upload_per_minute)
    data = file.file.read(settings.max_upload_bytes + 1)
    upload = validate_upload(file.filename, data, settings.max_upload_bytes)
    key = idempotency.validate_key(idempotency_key)
    document_id = uuid.uuid4()
    if key:
        existing = idempotency.claim(
            db, user.id, "resume_upload", key, hashlib.sha256(data).hexdigest(), document_id
        )
        if existing is not None:
            db.rollback()
            doc = service.get_document(db, user.id, existing)
            return _resume_out(doc, service.get_version(db, user.id, existing))
    doc, version = service.ingest_upload(db, store, settings, user.id, upload, document_id)
    return _resume_out(doc, version)


@router.get("", response_model=Page[ResumeOut])
def list_resumes(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=10_000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[ResumeOut]:
    total = db.execute(
        select(func.count()).select_from(ResumeDocument).where(ResumeDocument.user_id == user.id)
    ).scalar_one()
    docs = (
        db.execute(
            select(ResumeDocument)
            .where(ResumeDocument.user_id == user.id)
            .order_by(ResumeDocument.created_at.desc(), ResumeDocument.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    latest: dict[uuid.UUID, ResumeVersion] = {}
    if docs:
        for v in db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.document_id.in_([d.id for d in docs]))
            .order_by(ResumeVersion.version_no)
        ).scalars():
            latest[v.document_id] = v
    return Page(
        items=[_resume_out(d, latest[d.id]) for d in docs], total=total, limit=limit, offset=offset
    )


@router.get("/{document_id}", response_model=ResumeDetailOut)
def get_resume(
    document_id: uuid.UUID,
    version: int | None = Query(None, ge=1),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ResumeDetailOut:
    doc = service.get_document(db, user.id, document_id)
    chosen = service.get_version(db, user.id, document_id, version)
    versions = (
        db.execute(
            select(ResumeVersion)
            .where(ResumeVersion.document_id == document_id)
            .order_by(ResumeVersion.version_no)
        )
        .scalars()
        .all()
    )
    base = _resume_out(doc, versions[-1])
    return ResumeDetailOut(
        **base.model_dump(),
        normalized=chosen.normalized,
        versions=[_version_out(v) for v in versions],
    )


@router.put("/{document_id}/corrections", response_model=ResumeVersionOut)
def correct_resume(
    document_id: uuid.UUID,
    body: CorrectionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ResumeVersionOut:
    """Saves corrections as a NEW immutable version. 409 if `base_version_no` is not the latest."""
    service.get_document(db, user.id, document_id)
    base = service.get_version(db, user.id, document_id, body.base_version_no)
    version = service.create_corrected_version(
        db,
        user.id,
        document_id,
        base,
        body.block_edits,
        body.contact.model_dump(exclude_unset=True) if body.contact else {},
    )
    db.commit()
    return _version_out(version)


@router.delete("/{document_id}", status_code=204)
def delete_resume(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    store: BlobStore = Depends(get_store),
) -> Response:
    deletion.delete_resume(db, store, user.id, document_id, current_request_id())
    return Response(status_code=204)  # idempotent: deleting something already gone is not an error
