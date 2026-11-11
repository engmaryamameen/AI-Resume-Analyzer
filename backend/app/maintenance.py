"""Periodic housekeeping. Run `python -m app.cli maintenance` from cron or a systemd timer (daily).

Each step is independent and idempotent.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, exists, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.errors import ServiceUnavailable
from app.core.logging import get_logger
from app.db import idempotency
from app.db.models import (
    AccountToken,
    AnalysisRun,
    AuditEvent,
    GuestAllowance,
    GuestAnalysis,
    JobDescription,
    JobDescriptionVersion,
    ProcessingJob,
    ResumeDocument,
    ResumeVersion,
)
from app.db.models import Session as AuthSession
from app.documents.storage import BlobStore
from app.jobs import queue
from app.privacy import deletion

log = get_logger(__name__)
AUDIT_RETENTION = timedelta(days=365)
FINISHED_JOB_RETENTION_DAYS = 30
ORPHAN_FILE_GRACE = timedelta(hours=1)
MAINTENANCE_BATCH = 200
ROW_PURGE_BATCH = 1000


def expire_old_data(db: Session, store: BlobStore, retention_days: int) -> dict[str, int]:
    """Delete résumés and job descriptions with no activity inside the retention window."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    stale_resumes = db.execute(
        select(ResumeDocument.id, ResumeDocument.user_id)
        .where(
            ~exists().where(
                ResumeVersion.document_id == ResumeDocument.id, ResumeVersion.created_at >= cutoff
            )
        )
        .order_by(ResumeDocument.created_at, ResumeDocument.id)
        .limit(MAINTENANCE_BATCH)
    ).all()
    stale_jobs = db.execute(
        select(JobDescription.id, JobDescription.user_id)
        .where(
            ~exists().where(
                JobDescriptionVersion.job_id == JobDescription.id,
                JobDescriptionVersion.created_at >= cutoff,
            )
        )
        .order_by(JobDescription.created_at, JobDescription.id)
        .limit(MAINTENANCE_BATCH)
    ).all()
    counts = {"resumes": 0, "job_descriptions": 0, "skipped_busy": 0}
    for document_id, user_id in stale_resumes:
        try:
            counts["resumes"] += deletion.delete_resume(
                db, store, user_id, document_id, "retention", inactive_before=cutoff
            )
        except ServiceUnavailable:
            counts["skipped_busy"] += 1  # the user's job is running; the next run will get it
    for job_id, user_id in stale_jobs:
        try:
            counts["job_descriptions"] += deletion.delete_job_description(
                db, user_id, job_id, "retention", inactive_before=cutoff
            )
        except ServiceUnavailable:
            counts["skipped_busy"] += 1
    return counts


def remove_orphan_files(db: Session, store: BlobStore) -> int:
    """Delete stored files that no résumé version refers to (crash between write and commit, failed unlink)."""
    # Stream filesystem entries and query only one bounded key batch at a time.
    # Committing each read batch avoids an hours-long snapshot on a large volume.
    from itertools import islice

    threshold = (datetime.now(UTC) - ORPHAN_FILE_GRACE).timestamp()
    candidates = (key for key, modified in store.stored() if modified < threshold)
    removed = 0
    while batch := list(islice(candidates, ROW_PURGE_BATCH)):
        known = set(
            db.scalars(
                select(ResumeVersion.storage_key).where(ResumeVersion.storage_key.in_(batch))
            )
        )
        db.commit()
        for key in batch:
            if key not in known:
                store.delete(key)
                removed += 1
    return removed


def fail_stuck_targets(db: Session) -> int:
    """Mark résumé versions and analyses whose job is gone or finished as failed, so nothing stays pending."""

    def no_active_job(
        target_column: InstrumentedAttribute[uuid.UUID], kind: str
    ) -> ColumnElement[bool]:
        return ~exists().where(
            ProcessingJob.target_id == target_column,
            ProcessingJob.kind == kind,
            ProcessingJob.status.in_(("queued", "running")),
        )

    versions = (
        cast(
            CursorResult[Any],
            db.execute(
                update(ResumeVersion)
                .where(
                    ResumeVersion.status == "processing",
                    no_active_job(ResumeVersion.id, "extract_resume"),
                )
                .values(status="failed", error_code="job_lost")
            ),
        ).rowcount
        or 0
    )
    runs = (
        cast(
            CursorResult[Any],
            db.execute(
                update(AnalysisRun)
                .where(
                    AnalysisRun.status.in_(("queued", "running")),
                    no_active_job(AnalysisRun.id, "run_analysis"),
                )
                .values(status="failed", error_code="job_lost", completed_at=datetime.now(UTC))
            ),
        ).rowcount
        or 0
    )
    return versions + runs


def run_maintenance(db: Session, store: BlobStore, settings: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    # A guest reservation is now committed only with its complete workspace.
    # Never infer interruption from age: an older deployment may have left an
    # incomplete reservation while a request was still active. Normal expiry
    # removes those legacy rows without risking a live upload.
    expired_guests = list(
        db.execute(
            select(GuestAnalysis.user_id)
            .where(GuestAnalysis.expires_at <= now)
            .order_by(GuestAnalysis.expires_at)
            .limit(MAINTENANCE_BATCH)
        ).scalars()
    )
    for owner_id in expired_guests:
        deletion.delete_account(db, store, owner_id, None)
    result = expire_old_data(db, store, settings.retention_days)
    result["expired_guests"] = len(expired_guests)
    db.execute(
        delete(GuestAllowance).where(
            GuestAllowance.network_key.in_(
                select(GuestAllowance.network_key)
                .where(GuestAllowance.next_allowed_at <= now)
                .limit(ROW_PURGE_BATCH)
            )
        )
    )
    result["orphan_files"] = remove_orphan_files(db, store)
    result["stuck_targets"] = fail_stuck_targets(db)
    result["sessions"] = (
        cast(
            CursorResult[Any],
            db.execute(
                delete(AuthSession).where(
                    AuthSession.id.in_(
                        select(AuthSession.id)
                        .where(AuthSession.expires_at < now)
                        .limit(ROW_PURGE_BATCH)
                    )
                )
            ),
        ).rowcount
        or 0
    )
    result["audit_events"] = (
        cast(
            CursorResult[Any],
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.id.in_(
                        select(AuditEvent.id)
                        .where(AuditEvent.created_at < now - AUDIT_RETENTION)
                        .limit(ROW_PURGE_BATCH)
                    )
                )
            ),
        ).rowcount
        or 0
    )
    db.execute(
        delete(AccountToken).where(
            AccountToken.id.in_(
                select(AccountToken.id).where(AccountToken.expires_at <= now).limit(ROW_PURGE_BATCH)
            )
        )
    )
    result["idempotency_keys"] = idempotency.purge_expired(db)
    result["finished_jobs"] = queue.purge_finished(db, FINISHED_JOB_RETENTION_DAYS)
    db.commit()
    queue.refresh_depth_gauge(db)
    log.info("maintenance_done", extra={k: v for k, v in result.items()})
    return result
