"""Scrape-time database gauges: authoritative across replicas, with no document identifiers."""

import shutil
from datetime import UTC, datetime

from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ProcessingJob

BACKLOG_AGE = Gauge("job_backlog_oldest_seconds", "Age of oldest queued job", ["kind"])
EXPIRED_LEASES = Gauge("job_expired_leases", "Running jobs with expired leases")
STORAGE_FREE = Gauge("storage_free_bytes", "Free bytes on upload volume")
STORAGE_TOTAL = Gauge("storage_total_bytes", "Capacity of upload volume")
RETRYING = Gauge("job_retrying", "Queued jobs that have already been attempted")
LAST_PROGRESS = Gauge(
    "job_last_progress_age_seconds", "Seconds since a job last progressed (zero when queue empty)"
)


def refresh(db: Session, settings: Settings) -> None:
    now = datetime.now(UTC)
    rows: dict[str, datetime] = {
        kind: oldest
        for kind, oldest in db.execute(
            select(ProcessingJob.kind, func.min(ProcessingJob.created_at))
            .where(ProcessingJob.status == "queued")
            .group_by(ProcessingJob.kind)
        ).all()
    }
    for kind in ("extract_resume", "run_analysis"):
        oldest = rows.get(kind)
        BACKLOG_AGE.labels(kind).set(max(0, (now - oldest).total_seconds()) if oldest else 0)
    EXPIRED_LEASES.set(
        db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.status == "running", ProcessingJob.locked_until < now)
        )
        or 0
    )
    RETRYING.set(
        db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.status == "queued", ProcessingJob.attempts > 0)
        )
        or 0
    )
    last = db.scalar(select(func.max(ProcessingJob.updated_at)).where(ProcessingJob.attempts > 0))
    LAST_PROGRESS.set(
        max(0, (now - last).total_seconds())
        if rows and last
        else max((now - oldest).total_seconds() for oldest in rows.values())
        if rows
        else 0
    )
    usage = shutil.disk_usage(settings.storage_dir)
    STORAGE_FREE.set(usage.free)
    STORAGE_TOTAL.set(usage.total)
