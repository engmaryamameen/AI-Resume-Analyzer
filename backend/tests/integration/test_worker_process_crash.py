"""Kill an actual worker process in each transaction stage; lease fencing permits one recovery."""

import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db.models import AuditEvent, ProcessingJob, User
from app.db.session import session_scope
from app.jobs import queue, worker
from app.jobs.registry import JobKind

pytestmark = pytest.mark.integration

CHILD = r"""
import os, signal
from pathlib import Path
from app.jobs import worker, registry
from app.jobs.registry import JobKind
from app.ml.rules import RulesEngine
stage, marker = os.environ['CRASH_STAGE'], Path(os.environ['CRASH_MARKER'])
def hold(name):
    if stage == name:
        marker.write_text(name)
        signal.pause()
def prepare(db, target):
    hold('prepare')
    return str(target)
def compute(data, ctx):
    ctx.heartbeat()
    hold('compute')
    return data
def commit(db, target, result):
    from app.db.models import AuditEvent
    db.add(AuditEvent(action='fault-test.settled', target_id=str(target)))
    db.flush()
    hold('commit')
registry.register(JobKind('run_analysis', prepare, compute, commit, lambda *_: None, lambda *_: None))
worker.run_once(RulesEngine())
"""


@pytest.mark.parametrize("stage", ["prepare", "compute", "commit"])
def test_killed_worker_recovers_without_duplicate_commit(db_engine, tmp_path, monkeypatch, stage):
    owner_id, target_id = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner_id, email=f"{owner_id}@example.test", password_hash="!test"))
        db.flush()
        queue.enqueue(
            db, user_id=owner_id, kind="run_analysis", target_id=target_id, max_attempts=3
        )
    marker = tmp_path / "stage"
    env = {
        **os.environ,
        "CRASH_STAGE": stage,
        "CRASH_MARKER": str(marker),
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }
    child = subprocess.Popen(
        [sys.executable, "-c", CHILD], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), (
            child.communicate(timeout=1)[1]
            if child.poll() is not None
            else "worker did not reach stage"
        )
        child.kill()
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stderr.close()
    with session_scope() as db:
        row = db.scalar(select(ProcessingJob).where(ProcessingJob.target_id == target_id))
        assert row.status == "running"
        row.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "fault-test.settled")
            )
            == 0
        )
    with session_scope() as db:
        recovered = queue.claim_next(db, 30)
    assert recovered.attempts == 2

    def commit(db, target, result):
        db.add(AuditEvent(action="fault-test.settled", target_id=str(target)))

    kind = JobKind(
        "run_analysis", lambda *_: None, lambda *_: None, commit, lambda *_: None, lambda *_: None
    )
    worker._finish(recovered, kind, "recovered")
    worker._finish(recovered, kind, "duplicate")
    with session_scope() as db:
        assert db.get(ProcessingJob, recovered.id).status == "succeeded"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "fault-test.settled")
            )
            == 1
        )
