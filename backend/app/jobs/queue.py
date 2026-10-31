"""Durable PostgreSQL jobs with SKIP LOCKED claims, heartbeats and bounded retries.

One row per target prevents duplicate logical work; expired claims are reclaimed or failed."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.metrics import JOB_QUEUE_DEPTH, JOB_RETRIES
from app.db.models import ProcessingJob

MAX_BACKOFF_SECONDS = 300
KINDS = ("extract_resume", "run_analysis")


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: str
    target_id: uuid.UUID
    user_id: uuid.UUID
    attempts: int


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    db: Session, *, user_id: uuid.UUID, kind: str, target_id: uuid.UUID, max_attempts: int
) -> None:
    db.execute(
        pg_insert(ProcessingJob)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            kind=kind,
            target_id=target_id,
            max_attempts=max_attempts,
        )
        .on_conflict_do_nothing(constraint="uq_jobs_kind_target")
    )


def claim_next(db: Session, lock_seconds: int) -> ClaimedJob | None:
    now = _now()
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.next_run_at <= now,
            (ProcessingJob.status == "queued")
            | (
                (ProcessingJob.status == "running")
                & (ProcessingJob.locked_until < now)
                & (ProcessingJob.attempts < ProcessingJob.max_attempts)
            ),
        )
        .order_by(ProcessingJob.next_run_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None:
        db.rollback()
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_until = now + timedelta(seconds=lock_seconds)
    claimed = ClaimedJob(job.id, job.kind, job.target_id, job.user_id, job.attempts)
    db.commit()
    return claimed


def exhausted_candidates(db: Session, limit: int = 50) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Read candidates without row locks; settlement rechecks them under the user's advisory lock."""
    now = _now()
    return [
        tuple(row)
        for row in db.execute(
            select(ProcessingJob.id, ProcessingJob.user_id)
            .where(
                ProcessingJob.status == "running",
                ProcessingJob.locked_until < now,
                ProcessingJob.attempts >= ProcessingJob.max_attempts,
            )
            .order_by(ProcessingJob.locked_until)
            .limit(limit)
        ).all()
    ]


def touch(db: Session, job_id: uuid.UUID, attempts: int, lock_seconds: int) -> bool:
    """Renew only the still-live claim belonging to this attempt."""
    now = _now()
    result = db.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.id == job_id,
            ProcessingJob.status == "running",
            ProcessingJob.attempts == attempts,
            ProcessingJob.locked_until > now,
            ProcessingJob.cancel_requested.is_(False),
        )
        .values(locked_until=now + timedelta(seconds=lock_seconds))
    )
    return bool(cast(CursorResult[Any], result).rowcount)


def lock_job(db: Session, job_id: uuid.UUID) -> ProcessingJob | None:
    return db.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
    ).scalar_one_or_none()


def mark_succeeded(job: ProcessingJob) -> None:
    job.status, job.locked_until, job.last_error_code = "succeeded", None, None


def mark_cancelled(job: ProcessingJob) -> None:
    job.status, job.locked_until = "cancelled", None


def mark_failed(job: ProcessingJob, code: str) -> None:
    job.status, job.locked_until, job.last_error_code = "failed", None, code[:64]


def schedule_retry(job: ProcessingJob, code: str) -> None:
    delay = min(5 * 2 ** (job.attempts - 1), MAX_BACKOFF_SECONDS)
    job.status, job.locked_until, job.last_error_code = "queued", None, code[:64]
    job.next_run_at = _now() + timedelta(seconds=delay)
    JOB_RETRIES.labels(kind=job.kind).inc()


def cancel_for_target(
    db: Session, user_id: uuid.UUID, kind: str, target_id: uuid.UUID
) -> str | None:
    """Cancel a queued job at once, or flag a running one. Returns the job's status afterwards."""
    job = db.execute(
        select(ProcessingJob)
        .where(
            ProcessingJob.kind == kind,
            ProcessingJob.target_id == target_id,
            ProcessingJob.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if job is None:
        return None
    if job.status == "queued":
        mark_cancelled(job)
    elif job.status == "running":
        job.cancel_requested = True
    return job.status


def refresh_depth_gauge(db: Session) -> None:
    rows: dict[str, int] = {
        kind: count
        for kind, count in db.execute(
            select(ProcessingJob.kind, func.count())
            .where(ProcessingJob.status == "queued")
            .group_by(ProcessingJob.kind)
        ).all()
    }
    for kind in KINDS:
        JOB_QUEUE_DEPTH.labels(kind=kind).set(rows.get(kind, 0))


def purge_finished(db: Session, older_than_days: int) -> int:
    cutoff = _now() - timedelta(days=older_than_days)
    result = db.execute(
        delete(ProcessingJob).where(
            ProcessingJob.status.in_(("succeeded", "failed", "cancelled")),
            ProcessingJob.updated_at < cutoff,
        )
    )
    return cast(CursorResult[Any], result).rowcount or 0
