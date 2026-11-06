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
        with worker._lease_heartbeat(job):
            time.sleep(0.15)
