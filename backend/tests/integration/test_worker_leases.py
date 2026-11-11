"""Database-backed ownership checks for competing workers."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import ProcessingJob, User
from app.db.session import session_scope
from app.jobs import queue, worker
from app.jobs.registry import JobKind

pytestmark = pytest.mark.integration


def test_expired_worker_cannot_settle_reclaimed_attempt(db_engine):
    owner_id, target_id = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner_id, email=f"{owner_id}@example.test", password_hash="!test"))
        db.flush()
        queue.enqueue(db, user_id=owner_id, kind="run_analysis", target_id=target_id, max_attempts=3)
    with session_scope() as db:
        old = queue.claim_next(db, 30)
    assert old is not None
    with session_scope() as db:
        row = queue.lock_job(db, old.id)
        row.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    with session_scope() as db:
        new = queue.claim_next(db, 30)
    assert new is not None and new.id == old.id
    assert new.attempts == old.attempts + 1

    settled = []
    kind = JobKind(
        name="run_analysis", prepare=lambda *_: None, compute=lambda *_: None,
        commit=lambda *_: settled.append("committed"),
        on_failed=lambda *_: None, on_cancelled=lambda *_: None,
    )
    worker._finish(old, kind, "old-result")
    with session_scope() as db:
        row = db.get(ProcessingJob, old.id)
        assert row.status == "running" and row.attempts == new.attempts
        assert queue.touch(db, old.id, old.attempts, 30) is False
        assert queue.touch(db, new.id, new.attempts, 30) is True
    assert settled == []
    worker._finish(new, kind, "new-result")
    with session_scope() as db:
        assert db.get(ProcessingJob, old.id).status == "succeeded"
        assert queue.touch(db, new.id, new.attempts, 30) is False
    assert settled == ["committed"]


def test_cancellation_is_settled_instead_of_committing_result(db_engine):
    owner_id, target_id = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner_id, email=f"{owner_id}@example.test", password_hash="!test"))
        db.flush()
        queue.enqueue(db, user_id=owner_id, kind="run_analysis", target_id=target_id, max_attempts=3)
    with session_scope() as db:
        claim = queue.claim_next(db, 30)
    with session_scope() as db:
        queue.cancel_for_target(db, owner_id, "run_analysis", target_id)
    actions = []
    kind = JobKind(
        name="run_analysis", prepare=lambda *_: None, compute=lambda *_: None,
        commit=lambda *_: actions.append("committed"),
        on_failed=lambda *_: None, on_cancelled=lambda *_: actions.append("cancelled"),
    )
    worker._finish(claim, kind, "result")
    with session_scope() as db:
        assert db.get(ProcessingJob, claim.id).status == "cancelled"
    assert actions == ["cancelled"]


def test_competing_workers_only_claim_one_queued_job(db_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    owner_id, target_id = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner_id, email=f"{owner_id}@example.test", password_hash="!test"))
        db.flush()
        queue.enqueue(db, user_id=owner_id, kind="run_analysis", target_id=target_id, max_attempts=3)

    start = Barrier(2)

    def claim():
        start.wait(timeout=10)
        with session_scope() as db:
            return queue.claim_next(db, 30)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    claims = [item for item in results if item is not None]
    assert len(claims) == 1
    assert claims[0].attempts == 1


def test_final_settlement_prevents_reclaim_while_database_commit_is_pending(db_engine):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    owner_id, target_id = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner_id, email=f"{owner_id}@example.test", password_hash="!test"))
        db.flush()
        queue.enqueue(db, user_id=owner_id, kind="run_analysis", target_id=target_id, max_attempts=3)
    with session_scope() as db:
        claim = queue.claim_next(db, 1)
    assert claim is not None

    entered = threading.Event()
    release = threading.Event()
    committed = []

    def hold_settlement(_db, _target, _result):
        entered.set()
        assert release.wait(5)
        committed.append(True)

    kind = JobKind(
        name="run_analysis", prepare=lambda *_: None, compute=lambda *_: None,
        commit=hold_settlement, on_failed=lambda *_: None, on_cancelled=lambda *_: None,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker._finish, claim, kind, "result")
        try:
            assert entered.wait(5)
            time.sleep(1.1)
            with session_scope() as db:
                assert queue.claim_next(db, 1) is None
        finally:
            release.set()
        future.result(timeout=5)

    with session_scope() as db:
        row = db.get(ProcessingJob, claim.id)
        assert row.status == "succeeded" and row.attempts == 1
    assert committed == [True]
