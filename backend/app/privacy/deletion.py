"""Deletion workflows.

Rows are removed by cascading foreign keys; stored files are unlinked after the transaction commits,
because the database cannot reach the filesystem (anything that fails to unlink is caught by the
orphan-file sweep in app.maintenance). Every function first takes the user's advisory lock, so a
deletion waits for that user's in-flight job to commit instead of racing it (see app.db.locks).
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.locks import lock_user
from app.db.models import AuditEvent, JobDescription, ResumeDocument, ResumeVersion, User
from app.db.models import Session as AuthSession
from app.documents.storage import BlobStore

log = get_logger(__name__)


def _unlink(store: BlobStore, keys: list[str]) -> None:
    for key in keys:
        try:
            store.delete(key)
        except OSError as exc:
            log.error("blob_delete_failed", extra={"error_type": type(exc).__name__})


def delete_resume(
    db: Session, store: BlobStore, user_id: uuid.UUID, document_id: uuid.UUID, request_id: str | None
) -> bool:
    lock_user(db, user_id)
    document = db.execute(
        select(ResumeDocument).where(ResumeDocument.id == document_id, ResumeDocument.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if document is None:
        db.rollback()
        return False
    keys = list(db.execute(
        select(ResumeVersion.storage_key).where(ResumeVersion.document_id == document_id,
                                                ResumeVersion.storage_key.is_not(None))).scalars())
    db.delete(document)  # cascades: versions -> analysis runs -> matches
    db.add(AuditEvent(user_id=user_id, action="resume.deleted", target_type="resume",
                      target_id=str(document_id), request_id=request_id))
    db.commit()
    _unlink(store, keys)
    return True


def delete_job_description(db: Session, user_id: uuid.UUID, job_id: uuid.UUID, request_id: str | None) -> bool:
    lock_user(db, user_id)
    job = db.execute(
        select(JobDescription).where(JobDescription.id == job_id, JobDescription.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if job is None:
        db.rollback()
        return False
    db.delete(job)
    db.add(AuditEvent(user_id=user_id, action="job_description.deleted", target_type="job_description",
                      target_id=str(job_id), request_id=request_id))
    db.commit()
    return True


def delete_account(db: Session, store: BlobStore, user_id: uuid.UUID, request_id: str | None) -> bool:
    lock_user(db, user_id)
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        db.rollback()
        return False
    keys = list(db.execute(
        select(ResumeVersion.storage_key).where(ResumeVersion.user_id == user_id,
                                                ResumeVersion.storage_key.is_not(None))).scalars())
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    # The audit trail keeps an anonymous record (user_id becomes NULL through ON DELETE SET NULL).
    db.add(AuditEvent(user_id=None, action="account.deleted", target_type="user", request_id=request_id))
    db.delete(user)  # cascades to every private table, including queued and running jobs
    db.commit()
    _unlink(store, keys)
    return True
