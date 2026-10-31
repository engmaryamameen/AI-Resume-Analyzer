"""Guest uploads use the ordinary worker while quota and report access remain independent."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.main import app
from app.core.ratelimit import limiter
from app.db.models import GuestAllowance, GuestAnalysis, ProcessingJob, ResumeVersion, User
from app.db.session import session_scope
from app.documents.storage import LocalPrivateStore
from app.core.config import get_settings
from app.maintenance import run_maintenance
from tests.helpers import SAMPLE_RESUME, make_docx

pytestmark = pytest.mark.integration
API = "/api/v1/guest"
ORIGIN = {"Origin": "http://localhost:3000"}
JD = "Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n- 3+ years of experience"


def submit(client, *, key=None, data=None):
    return client.post(API + "/analyze", headers={**ORIGIN, "Idempotency-Key": key or str(uuid.uuid4())}, data={"job_text": JD}, files={"file": data or ("cv.docx", make_docx(SAMPLE_RESUME.splitlines()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})


def complete(client, run_jobs):
    run_jobs()
    first = client.post(API + "/progress", headers=ORIGIN)
    assert first.status_code == 200, first.text
    run_jobs()
    return client.post(API + "/progress", headers=ORIGIN)


def test_guest_can_analyze_without_auth_and_report_is_private(client, db_engine, run_jobs):
    result = submit(client)
    assert result.status_code == 202, result.text
    assert client.get("/api/v1/auth/me").status_code == 401
    done = complete(client, run_jobs)
    assert done.status_code == 200, done.text
    state = done.json()
    assert state["status"] == "succeeded" and state["report"]["engine"]["mode"] == "rules"
    assert state["available"] is False and state["report"]["matches"]
    with TestClient(app) as stranger:
        assert stranger.get(API).json()["report"] is None
        assert stranger.post(API + "/progress", headers=ORIGIN).status_code == 404
    cookie = next(c for c in client.cookies.jar if c.name == "mn_guest")
    assert cookie.has_nonstandard_attr("HttpOnly")


def test_quota_survives_cookie_loss_and_limiter_restart(client, db_engine):
    assert submit(client).status_code == 202
    client.cookies.clear()
    limiter.reset()
    blocked = submit(client)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "guest_limit"
    assert client.get(API).json()["available"] is False


def test_retry_reuses_one_upload_and_does_not_reset_deadline(client, db_engine):
    key = str(uuid.uuid4())
    first = submit(client, key=key)
    again = submit(client, key=key)
    assert first.status_code == again.status_code == 202
    assert first.json()["next_allowed_at"] == again.json()["next_allowed_at"]
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(ProcessingJob)) == 1
        assert db.scalar(select(func.count()).select_from(GuestAnalysis)) == 1


def test_failed_extraction_restores_allowance_and_retry_works(client, db_engine, run_jobs):
    key = str(uuid.uuid4())
    assert submit(client, key=key, data=("bad.pdf", b"%PDF-1.4\nnot-a-pdf", "application/pdf")).status_code == 202
    run_jobs()
    failed = client.post(API + "/progress", headers=ORIGIN).json()
    assert failed["status"] == "failed" and failed["available"] is True
    assert submit(client, key=key).status_code == 202
    assert complete(client, run_jobs).json()["status"] == "succeeded"


def test_deleting_guest_report_removes_private_data_but_keeps_quota(client, db_engine, run_jobs):
    assert submit(client).status_code == 202
    assert complete(client, run_jobs).json()["status"] == "succeeded"
    with session_scope() as db:
        key = db.scalar(select(ResumeVersion.storage_key))
    store = LocalPrivateStore(get_settings().storage_dir)
    assert store.path(key).exists()
    assert client.delete(API, headers=ORIGIN).status_code == 204
    assert not store.path(key).exists()
    assert client.get(API).json()["available"] is False
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(GuestAllowance)) == 1
    assert submit(client).status_code == 429


def test_allowance_resets_after_24_hours_and_old_workspace_is_removed(client, db_engine, monkeypatch):
    from app.guest import router
    assert submit(client).status_code == 202
    now = datetime.now(UTC) + timedelta(hours=24, seconds=1)
    monkeypatch.setattr(router, "_now", lambda: now)
    assert client.get(API).json()["available"] is True
    assert submit(client).status_code == 202
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_cross_origin_guest_writes_are_rejected_before_data_is_stored(client, db_engine):
    response = client.post(API + "/analyze", headers={"Origin": "https://attacker.invalid", "Idempotency-Key": str(uuid.uuid4())}, data={"job_text": JD}, files={"file": ("cv.docx", make_docx(SAMPLE_RESUME.splitlines()))})
    assert response.status_code == 403
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_simultaneous_requests_reserve_only_one_guest_allowance(db_engine):
    def attempt(_):
        with TestClient(app) as c:
            return submit(c).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [202, 429]


def test_cleanup_expires_guest_data_without_refunding_a_current_allowance(client, db_engine, run_jobs):
    assert submit(client).status_code == 202
    run_jobs()
    with session_scope() as db:
        guest = db.scalar(select(GuestAnalysis))
        guest.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with session_scope() as db:
        result = run_maintenance(db, LocalPrivateStore(get_settings().storage_dir), get_settings())
        assert result["expired_guests"] == 1
    assert client.get(API).json()["available"] is False
