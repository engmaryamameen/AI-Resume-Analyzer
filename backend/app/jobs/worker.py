"""Worker process: `python -m app.jobs.worker`.

Owns every terminal job transition. Work happens outside any transaction (see jobs/registry.py); the
result and the job's final status are committed together under the user's advisory lock, after
re-reading the cancel flag, so cancellation and deletion can never interleave with a half-written result.
"""

import signal
import time
import uuid

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.hardening import harden_process
from app.core.logging import configure_logging, get_logger, request_id_var
from app.db.locks import lock_user
from app.db.session import session_scope
from app.jobs import handlers, queue, registry  # noqa: F401  (handlers registers the job kinds)
from app.jobs.queue import ClaimedJob
from app.jobs.registry import JobContext, JobKind, Transient
from app.ml.engine import Engine, load_engine

log = get_logger(__name__)
_stop = False


def _heartbeat(job: ClaimedJob):
    lock_seconds = get_settings().job_lock_seconds

    def beat() -> None:
        with session_scope() as db:
            if not queue.touch(db, job.id, job.attempts, lock_seconds):
                raise Transient("lease_lost")

    return beat


def _finish(job: ClaimedJob, kind: JobKind, result: object | None) -> None:
    with session_scope() as db:
        lock_user(db, job.user_id)
        row = queue.lock_job(db, job.id)
        if row is None or row.status != "running" or row.attempts != job.attempts or (
            row.locked_until is None or row.locked_until <= queue._now()
        ):
            return  # deleted meanwhile, or already settled by another attempt
        if row.cancel_requested:
            kind.on_cancelled(db, job.target_id)
            queue.mark_cancelled(row)
            return
        if result is not None:
            kind.commit(db, job.target_id, result)
        queue.mark_succeeded(row)


def _fail_or_retry(job: ClaimedJob, kind: JobKind, code: str, *, retryable: bool) -> None:
    with session_scope() as db:
        lock_user(db, job.user_id)
        row = queue.lock_job(db, job.id)
        if row is None or row.status != "running" or row.attempts != job.attempts or (
            row.locked_until is None or row.locked_until <= queue._now()
        ):
            return
        if row.cancel_requested:
            kind.on_cancelled(db, job.target_id)
            queue.mark_cancelled(row)
        elif retryable and row.attempts < row.max_attempts:
            queue.schedule_retry(row, code)
        else:
            queue.mark_failed(row, code)
            kind.on_failed(db, job.target_id, code)


def _execute(job: ClaimedJob, engine: Engine) -> None:
    kind = registry.get(job.kind)
    try:
        with session_scope() as db:
            prepared = kind.prepare(db, job.target_id)
        result = None if prepared is None else kind.compute(prepared, JobContext(engine, _heartbeat(job)))
        _finish(job, kind, result)
    except Transient as exc:
        _fail_or_retry(job, kind, exc.code, retryable=True)
    except AppError as exc:  # deterministic: retrying cannot help
        _fail_or_retry(job, kind, exc.code, retryable=False)
    except Exception as exc:  # noqa: BLE001 - boundary: record and retry within bounds, never crash the loop
        log.error("job_error", extra={"kind": job.kind, "error_type": type(exc).__name__})
        _fail_or_retry(job, kind, f"unexpected_{type(exc).__name__}", retryable=True)


def _settle_exhausted() -> bool:
    # Lock order matches deletion and completion: user advisory lock, then job row.
    # Each failed job and its target are settled atomically in the same transaction.
    with session_scope() as db:
        candidates = queue.exhausted_candidates(db)
    settled = False
    for job_id, user_id in candidates:
        with session_scope() as db:
            lock_user(db, user_id)
            row = queue.lock_job(db, job_id)
            if row is None or row.status != "running" or row.locked_until is None:
                continue
            if row.locked_until >= queue._now() or row.attempts < row.max_attempts:
                continue
            kind = registry.get(row.kind)
            if row.cancel_requested:
                kind.on_cancelled(db, row.target_id)
                queue.mark_cancelled(row)
            else:
                kind.on_failed(db, row.target_id, "worker_lost")
                queue.mark_failed(row, "worker_lost")
            settled = True
    return settled


def run_once(engine: Engine) -> bool:
    """Process at most one job. Returns False when there was nothing to do."""
    settled = _settle_exhausted()
    with session_scope() as db:
        job = queue.claim_next(db, get_settings().job_lock_seconds)
    if job is None:
        return settled
    token = request_id_var.set(f"job-{uuid.uuid4().hex[:12]}")
    try:
        _execute(job, engine)
        log.info("job_done", extra={"kind": job.kind, "attempt": job.attempts})
    finally:
        request_id_var.reset(token)
    return True


def run_until_idle(engine: Engine, max_jobs: int = 50) -> None:
    for _ in range(max_jobs):
        if not run_once(engine):
            return


def main() -> None:
    configure_logging()
    harden_process()
    engine = load_engine(get_settings())
    log.info("worker_started", extra={"engine_mode": engine.info.mode})

    def _shutdown(*_: object) -> None:
        global _stop
        _stop = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    while not _stop:
        try:
            if not run_once(engine):
                time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001 - e.g. the database briefly unavailable
            log.error("worker_loop_error", extra={"error_type": type(exc).__name__})
            time.sleep(3.0)
    log.info("worker_stopped")


if __name__ == "__main__":
    main()
