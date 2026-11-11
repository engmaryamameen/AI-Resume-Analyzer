"""Independent lease renewal during a blocking compute call."""
import time
import uuid

import pytest

from app.jobs import worker
from app.jobs.queue import ClaimedJob
from app.jobs.registry import Transient


def test_lease_renewed_during_blocking_inference(monkeypatch):
    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    beats = []
    monkeypatch.setattr(worker, "_heartbeat", lambda _: lambda: beats.append(time.monotonic()))
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    with worker._lease_heartbeat(job):
        time.sleep(0.27)
    assert len(beats) >= 2


def test_lost_lease_prevents_commit_after_blocking_call(monkeypatch):
    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    monkeypatch.setattr(worker, "_heartbeat", lambda _: lambda: (_ for _ in ()).throw(Transient("lease_lost")))
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    with pytest.raises(Transient, match="lease_lost"):
        with worker._lease_heartbeat(job) as heartbeat:
            time.sleep(0.15)
            heartbeat()


def test_heartbeat_remains_active_until_settlement_returns(monkeypatch):
    from app.jobs.registry import JobKind

    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    beats = []
    monkeypatch.setattr(worker, "_heartbeat", lambda _: lambda: beats.append(time.monotonic()))
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    monkeypatch.setattr(worker.registry, "get", lambda _: JobKind(
        name="run_analysis", prepare=lambda *_: None, compute=lambda *_: None,
        commit=lambda *_: None, on_failed=lambda *_: None, on_cancelled=lambda *_: None,
    ))
    from contextlib import contextmanager

    @contextmanager
    def session():
        yield object()

    monkeypatch.setattr(worker, "session_scope", session)

    def settle(*_):
        before = len(beats)
        time.sleep(0.3)
        assert len(beats) > before

    monkeypatch.setattr(worker, "_finish", settle)
    worker._execute(job, object())


def test_worker_does_not_finalize_after_losing_lease(monkeypatch):
    from contextlib import contextmanager
    from app.jobs.registry import JobKind

    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    monkeypatch.setattr(worker, "_heartbeat", lambda _: lambda: (_ for _ in ()).throw(Transient("lease_lost")))
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    monkeypatch.setattr(worker.registry, "get", lambda _: JobKind(
        name="run_analysis", prepare=lambda *_: "work", compute=lambda *_: "result",
        commit=lambda *_: None, on_failed=lambda *_: None, on_cancelled=lambda *_: None,
    ))

    @contextmanager
    def session():
        yield object()

    monkeypatch.setattr(worker, "session_scope", session)
    finalized = []
    monkeypatch.setattr(worker, "_finish", lambda *args, **kwargs: finalized.append(True))
    errors = []
    monkeypatch.setattr(worker, "_fail_or_retry", lambda *args, **kwargs: errors.append(args[2]))
    worker._execute(job, object())
    assert finalized == []
    assert errors == ["lease_lost"]


def test_heartbeat_shutdown_stops_future_renewals(monkeypatch):
    import threading

    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def renew():
        calls.append(1)
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(worker, "_heartbeat", lambda _: renew)
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    with worker._lease_heartbeat(job):
        assert entered.wait(3)
        release.set()
    count = len(calls)
    time.sleep(0.15)
    assert len(calls) == count


def test_settlement_serializes_with_renewal(monkeypatch):
    import threading
    from contextlib import contextmanager

    job = ClaimedJob(uuid.uuid4(), "run_analysis", uuid.uuid4(), uuid.uuid4(), 1)
    settled = threading.Event()
    allow_commit = threading.Event()
    renewed_during_settlement = []

    class FakeDB:
        def commit(self):
            settled.set()
            assert allow_commit.wait(3)

    @contextmanager
    def session():
        yield FakeDB()

    monkeypatch.setattr(worker, "session_scope", session)
    monkeypatch.setattr(worker, "lock_user", lambda *_: None)
    monkeypatch.setattr(worker.queue, "lock_job", lambda *_: None)
    monkeypatch.setattr(worker, "get_settings", lambda: type("Settings", (), {"job_lock_seconds": 0.3})())
    monkeypatch.setattr(worker, "_heartbeat", lambda _: lambda: renewed_during_settlement.append(settled.is_set()))
    kind = worker.JobKind(
        name="run_analysis", prepare=lambda *_: None, compute=lambda *_: None,
        commit=lambda *_: None, on_failed=lambda *_: None, on_cancelled=lambda *_: None,
    )
    lock = threading.Lock()
    from concurrent.futures import ThreadPoolExecutor
    with worker._lease_heartbeat(job, lock):
        with ThreadPoolExecutor(max_workers=1) as pool:
            finished = pool.submit(worker._finish, job, kind, None, lock)
            assert settled.wait(3)
            time.sleep(0.15)
            assert not any(renewed_during_settlement)
            allow_commit.set()
            finished.result(timeout=3)
