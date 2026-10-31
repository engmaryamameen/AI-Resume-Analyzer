"""Deletion workflows.

Rows are removed by cascading foreign keys; stored files are unlinked after the transaction commits,
because the database cannot reach the filesystem (anything that fails to unlink is caught by the
orphan-file sweep in app.maintenance). Every function first takes the user's advisory lock, so a
deletion waits for that user's in-flight job to commit instead of racing it (see app.db.locks).
"""

import uuid

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.logging import get_logger
from app.db.locks import lock_user
from app.db.models import (
    AnalysisRun,
    AuditEvent,
    IdempotencyKey,
    JobDescription,
    JobDescriptionVersion,
    ProcessingJob,
    ResumeDocument,
    ResumeVersion,
    User,
)
from app.db.models import Session as AuthSession
from app.documents.storage import BlobStore

log = get_logger(__name__)


def _unlink(store: BlobStore, keys: list[str | None]) -> None:
    for key in keys:
        if key is None:
            continue
        try:
            store.delete(key)
        except OSError as exc:
            log.error("blob_delete_failed", extra={"error_type": type(exc).__name__})


def _delete_derived_jobs(
    db: Session,
    user_id: uuid.UUID,
    run_ids: Select[tuple[uuid.UUID]],
    version_ids: Select[tuple[uuid.UUID]] | None = None,
) -> None:
    targets = [and_(ProcessingJob.kind == "run_analysis", ProcessingJob.target_id.in_(run_ids))]
    if version_ids is not None:
        targets.append(
            and_(ProcessingJob.kind == "extract_resume", ProcessingJob.target_id.in_(version_ids))
        )
    db.execute(delete(ProcessingJob).where(ProcessingJob.user_id == user_id, or_(*targets)))


def delete_resume(
    db: Session,
    store: BlobStore,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    request_id: str | None,
) -> bool:
    lock_user(db, user_id)
    document = db.execute(
        select(ResumeDocument)
        .where(ResumeDocument.id == document_id, ResumeDocument.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if document is None:
        db.rollback()
        return False
    keys = list(
        db.execute(
            select(ResumeVersion.storage_key).where(
                ResumeVersion.document_id == document_id, ResumeVersion.storage_key.is_not(None)
            )
        ).scalars()
    )
    version_ids = select(ResumeVersion.id).where(ResumeVersion.document_id == document_id)
    run_ids = select(AnalysisRun.id).where(AnalysisRun.resume_version_id.in_(version_ids))
    # Queue targets and idempotency results are polymorphic UUIDs, not foreign keys.
    # Remove them before cascading away the rows needed to find them. The per-user
    # advisory lock also fences a worker that is computing outside a transaction.
    _delete_derived_jobs(db, user_id, run_ids, version_ids)
    db.execute(
        delete(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            or_(
                and_(
                    IdempotencyKey.scope == "resume_upload", IdempotencyKey.result_id == document_id
                ),
                and_(IdempotencyKey.scope == "analysis", IdempotencyKey.result_id.in_(run_ids)),
            ),
        )
    )
    db.delete(document)  # cascades: versions -> analysis runs -> matches
    db.add(
        AuditEvent(
            user_id=user_id,
            action="resume.deleted",
            target_type="resume",
            target_id=str(document_id),
            request_id=request_id,
        )
    )
    db.commit()
    _unlink(store, keys)
    return True


def delete_job_description(
    db: Session, user_id: uuid.UUID, job_id: uuid.UUID, request_id: str | None
) -> bool:
    lock_user(db, user_id)
    job = db.execute(
        select(JobDescription)
        .where(JobDescription.id == job_id, JobDescription.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if job is None:
        db.rollback()
        return False
    version_ids = select(JobDescriptionVersion.id).where(JobDescriptionVersion.job_id == job_id)
    run_ids = select(AnalysisRun.id).where(AnalysisRun.jd_version_id.in_(version_ids))
    _delete_derived_jobs(db, user_id, run_ids)
    db.execute(
        delete(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == "analysis",
            IdempotencyKey.result_id.in_(run_ids),
        )
    )
    db.delete(job)
    db.add(
        AuditEvent(
            user_id=user_id,
            action="job_description.deleted",
            target_type="job_description",
            target_id=str(job_id),
            request_id=request_id,
        )
    )
    db.commit()
    return True


def delete_account(
    db: Session, store: BlobStore, user_id: uuid.UUID, request_id: str | None
) -> bool:
    lock_user(db, user_id)
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        db.rollback()
        return False
    keys = list(
        db.execute(
            select(ResumeVersion.storage_key).where(
                ResumeVersion.user_id == user_id, ResumeVersion.storage_key.is_not(None)
            )
        ).scalars()
    )
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    # The audit trail keeps an anonymous record (user_id becomes NULL through ON DELETE SET NULL).
    db.add(
        AuditEvent(
            user_id=None, action="account.deleted", target_type="user", request_id=request_id
        )
    )
    db.delete(user)  # cascades to every private table, including queued and running jobs
    db.commit()
    _unlink(store, keys)
    return True
