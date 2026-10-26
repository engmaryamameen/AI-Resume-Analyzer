"""End-to-end API + database workflows. Requires a DISPOSABLE PostgreSQL (TEST_DATABASE_URL).

The worker is driven in-process with the rule-based engine; learned models are not involved.
"""

import dataclasses
import os
import uuid

import pytest
from sqlalchemy import func, select, text

from app.db.models import AnalysisRun, ProcessingJob, ResumeVersion, User
from app.db.session import session_scope
from app.jobs import registry
from tests.helpers import SAMPLE_RESUME, make_docx

pytestmark = pytest.mark.integration
API = "/api/v1"
PASSWORD = "correct horse battery staple"
JD = ("Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n"
      "- 3+ years of experience\nNice to have:\n- Experience with Rust\n")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_file(text: str = SAMPLE_RESUME):
    return {"file": ("cv.docx", make_docx([line for line in text.splitlines() if line.strip()]), DOCX_MIME)}


def upload(c, key=None, files=None):
    return c.post(f"{API}/resumes", files=files or docx_file(), headers={"Idempotency-Key": key} if key else {})


def ready_resume(c, run_jobs):
    r = upload(c).json()
    run_jobs()
    detail = c.get(f"{API}/resumes/{r['id']}").json()
    assert detail["latest_version"]["status"] == "ready", detail
    return r["id"], detail["latest_version"]["id"]


def make_job(c):
    j = c.post(f"{API}/job-descriptions", json={"title": "Role", "text": JD})
    assert j.status_code == 201, j.text
    return j.json()["id"], j.json()["latest_version"]["id"]


def analyse(c, rv, jv, key=None):
    return c.post(f"{API}/analyses", json={"resume_version_id": rv, "jd_version_id": jv},
                  headers={"Idempotency-Key": key} if key else {})


def statuses(detail):
    return {m["requirement"]["text"]: m["status"] for m in detail["matches"]}


def count(model):
    with session_scope() as db:
        return db.execute(select(func.count()).select_from(model)).scalar_one()


def make_runnable_now() -> None:
    with session_scope() as db:
        db.execute(text("UPDATE processing_jobs SET next_run_at = now() WHERE status = 'queued'"))


def test_full_workflow_from_upload_to_report(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run = analyse(c, rv, jv, key="analysis-key-0001")
    assert run.status_code == 202 and run.json()["status"] == "queued"
    run_jobs()
    detail = c.get(f"{API}/analyses/{run.json()['id']}").json()
    assert detail["status"] == "succeeded" and detail["engine"]["mode"] == "rules"
    assert {a["id"] for a in detail["assessments"]} == {
        "requirement_evidence", "document_structure", "writing_style", "extraction_reliability"}
    by_name = statuses(detail)
    assert by_name["Python"] == "supported" and by_name["Kubernetes"] == "mentioned_only" and by_name["Rust"] == "no_evidence"
    assert detail["staleness"] == {"is_stale": False, "reasons": []}
    for fmt, media in (("json", "application/json"), ("csv", "text/csv"), ("md", "text/markdown")):
        r = c.get(f"{API}/analyses/{detail['id']}/report", params={"format": fmt})
        assert r.status_code == 200 and r.headers["content-type"].startswith(media)
        assert r.headers["content-disposition"].startswith("attachment")
        assert "alex.tester@example.com" not in r.text  # contact details never exported


def test_duplicate_upload_with_same_key_creates_one_logical_document(make_user, run_jobs):
    _, c = make_user()
    a, b = upload(c, "upload-key-0001"), upload(c, "upload-key-0001")
    assert a.json()["id"] == b.json()["id"]
    assert count(ResumeVersion) == 1 and count(ProcessingJob) == 1
    other = upload(c, "upload-key-0001", files=docx_file("Someone Else\nSKILLS\nGo\n"))
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"


def test_duplicate_analysis_request_returns_the_same_analysis(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    a, b = analyse(c, rv, jv, "same-key-000001"), analyse(c, rv, jv, "same-key-000001")
    assert a.json()["id"] == b.json()["id"] and count(AnalysisRun) == 1


@pytest.mark.security
def test_users_cannot_see_or_use_each_others_data(make_user, run_jobs):
    _, a = make_user("a@example.com")
    _, b = make_user("b@example.com")
    doc_id, rv = ready_resume(a, run_jobs)
    _, jv = make_job(a)
    run_id = analyse(a, rv, jv).json()["id"]
    run_jobs()
    for url in (f"/resumes/{doc_id}", f"/analyses/{run_id}", f"/analyses/{run_id}/report"):
        assert b.get(API + url).status_code == 404
    _, b_jv = make_job(b)
    assert analyse(b, rv, b_jv).status_code == 404                   # A's résumé version
    assert b.delete(f"{API}/resumes/{doc_id}").status_code == 204    # idempotent no-op for B
    assert a.get(f"{API}/resumes/{doc_id}").status_code == 200       # A's data untouched
    assert b.get(f"{API}/resumes").json()["total"] == 0


@pytest.mark.security
def test_state_changing_requests_need_csrf_token(make_user):
    _, c = make_user()
    c.headers.pop("X-CSRF-Token")
    r = c.post(f"{API}/job-descriptions", json={"title": "x", "text": JD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"


@pytest.mark.security
def test_admin_comes_only_from_the_database_role_and_never_from_registration(make_user):
    email, user = make_user("root@example.com")
    assert user.get(f"{API}/admin/overview").status_code == 403   # registering never grants a role
    with session_scope() as db:
        db.execute(text("UPDATE users SET role = 'admin' WHERE email = :e"), {"e": email})
    r = user.get(f"{API}/admin/overview")
    assert r.status_code == 200 and "root@example.com" not in r.text   # counts only, no content


@pytest.mark.security
def test_the_cli_is_the_way_to_grant_admin(make_user):
    from app.cli import main

    email, _ = make_user("ops@example.com")
    assert main(["grant-admin", email]) == 0
    with session_scope() as db:
        assert db.execute(select(User.role).where(User.email == email)).scalar_one() == "admin"
    assert main(["grant-admin", "nobody@example.com"]) == 1


def test_failed_extraction_never_produces_a_usable_analysis(make_user, run_jobs):
    _, c = make_user()
    bad = {"file": ("cv.pdf", b"%PDF-1.4\nnot really a pdf\n%%EOF", "application/pdf")}
    r = upload(c, files=bad).json()
    run_jobs()   # a corrupt file is a deterministic failure: no retries
    v = c.get(f"{API}/resumes/{r['id']}").json()["latest_version"]
    assert v["status"] == "failed" and v["error_code"] == "pdf_corrupt"
    _, jv = make_job(c)
    attempt = analyse(c, v["id"], jv)
    assert attempt.status_code == 409 and attempt.json()["error"]["code"] == "version_not_ready"
    assert count(AnalysisRun) == 0


def test_unexpected_failures_are_retried_within_bounds_and_leave_no_results(make_user, run_jobs, monkeypatch):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run_id = analyse(c, rv, jv).json()["id"]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash")

    monkeypatch.setitem(registry._KINDS, "run_analysis", dataclasses.replace(registry.get("run_analysis"), compute=boom))
    for _ in range(5):
        run_jobs()
        make_runnable_now()
    a = c.get(f"{API}/analyses/{run_id}").json()
    assert a["status"] == "failed" and a["error_code"] == "unexpected_RuntimeError"
    assert a["assessments"] is None and a["matches"] == []
    with session_scope() as db:
        job = db.execute(select(ProcessingJob).where(ProcessingJob.kind == "run_analysis")).scalar_one()
        assert job.status == "failed" and job.attempts == job.max_attempts


def test_a_job_whose_worker_disappeared_is_settled_as_failed_not_left_running(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run_id = analyse(c, rv, jv).json()["id"]
    with session_scope() as db:   # a worker claimed the last attempt and then vanished
        db.execute(text("UPDATE processing_jobs SET status='running', attempts=max_attempts, "
                        "locked_until = now() - interval '1 minute' WHERE kind='run_analysis'"))
        db.execute(text("UPDATE analysis_runs SET status='running'"))
    run_jobs()
    a = c.get(f"{API}/analyses/{run_id}").json()
    assert a["status"] == "failed" and a["error_code"] == "worker_lost"


def test_cancel_before_processing(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run_id = analyse(c, rv, jv).json()["id"]
    assert c.post(f"{API}/analyses/{run_id}/cancel").json()["status"] == "cancelled"
    run_jobs()
    assert c.get(f"{API}/analyses/{run_id}").json()["status"] == "cancelled"


def test_deleting_a_resume_during_a_queued_analysis_is_safe(make_user, run_jobs):
    _, c = make_user()
    doc_id, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run_id = analyse(c, rv, jv).json()["id"]
    assert c.delete(f"{API}/resumes/{doc_id}").status_code == 204
    run_jobs()                                  # nothing is left to write, and the worker must not crash
    assert count(AnalysisRun) == 0
    assert c.get(f"{API}/analyses/{run_id}").status_code == 404
    assert c.get(f"{API}/analyses/{run_id}/report").status_code == 404   # an old report link is dead


def test_a_résumé_can_be_deleted_in_every_state(make_user, run_jobs):
    _, c = make_user()
    queued = upload(c).json()["id"]                       # still waiting for extraction
    assert c.delete(f"{API}/resumes/{queued}").status_code == 204
    bad = upload(c, files={"file": ("cv.pdf", b"%PDF-1.4\nnope\n%%EOF", "application/pdf")}).json()["id"]
    run_jobs()                                            # now failed
    assert c.delete(f"{API}/resumes/{bad}").status_code == 204
    assert count(ResumeVersion) == 0 and count(ProcessingJob) == 0


def test_resume_deletion_removes_the_stored_file(make_user, run_jobs):
    _, c = make_user()
    doc_id, _ = ready_resume(c, run_jobs)
    with session_scope() as db:
        key = db.execute(select(ResumeVersion.storage_key)).scalar_one()
    from app.core.config import get_settings

    path = get_settings().storage_dir / key[:2] / key
    assert path.exists()
    c.delete(f"{API}/resumes/{doc_id}")
    assert not path.exists()


def test_account_deletion_needs_the_password_and_removes_everything(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    analyse(c, rv, jv)
    run_jobs()
    wrong = c.post(f"{API}/auth/delete-account", json={"password": "not the password"})
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "password_incorrect" and c.get(f"{API}/auth/me").status_code == 200
    assert c.post(f"{API}/auth/delete-account", json={"password": PASSWORD}).status_code == 204
    assert c.get(f"{API}/auth/me").status_code == 401
    with session_scope() as db:
        for table in ("users", "resume_documents", "resume_versions", "job_descriptions", "analysis_runs",
                      "requirement_matches", "processing_jobs", "sessions", "idempotency_keys"):
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0, table
        audit = db.execute(text("SELECT count(*) FROM audit_events WHERE user_id IS NOT NULL")).scalar_one()
        assert audit == 0   # the audit trail is anonymised, not erased


def test_a_correction_creates_a_new_version_and_everything_derived_follows_it(make_user, run_jobs):
    _, c = make_user()
    doc_id, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    first = analyse(c, rv, jv).json()["id"]
    run_jobs()
    assert statuses(c.get(f"{API}/analyses/{first}").json())["Python"] == "supported"

    blocks = c.get(f"{API}/resumes/{doc_id}").json()["normalized"]["blocks"]
    bullet = next(b for b in blocks if b["text"].startswith("Built a billing API"))
    r = c.put(f"{API}/resumes/{doc_id}/corrections", json={
        "base_version_no": 1, "block_edits": {bullet["id"]: "Built a billing API used by 30 internal teams"},
        "contact": {"name": "Alex T. Tester"}})
    assert r.status_code == 200 and r.json()["version_no"] == 2 and r.json()["source"] == "user_correction"
    stale = c.put(f"{API}/resumes/{doc_id}/corrections", json={"base_version_no": 1, "block_edits": {}})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_base_version"

    old = c.get(f"{API}/analyses/{first}").json()
    assert old["staleness"]["is_stale"] and "resume_version_superseded" in old["staleness"]["reasons"]

    second = analyse(c, r.json()["id"], jv).json()["id"]
    run_jobs()
    assert statuses(c.get(f"{API}/analyses/{second}").json())["Python"] == "mentioned_only"   # now only listed
    cmp = c.get(f"{API}/analyses/compare", params={"base": first, "target": second}).json()
    assert cmp["like_for_like"] and not cmp["notes"]
    assert {"requirement": "Python", "before": "supported", "after": "mentioned_only", "change": "weaker"} in cmp["requirement_changes"]


def test_requirement_correction_versions_the_job_description(make_user, run_jobs):
    _, c = make_user()
    jd_id, _ = make_job(c)
    detail = c.get(f"{API}/job-descriptions/{jd_id}").json()
    keep = [{"id": r["id"], "text": r["text"], "kind": r["kind"], "category": r["category"]}
            for r in detail["requirements"] if r["text"] != "Rust" and r["origin"] == "extracted"]
    keep.append({"text": "Strong written communication", "kind": "required", "category": "soft_skill"})
    r = c.put(f"{API}/job-descriptions/{jd_id}/requirements", json={"base_version_no": 1, "requirements": keep})
    assert r.status_code == 200 and r.json()["latest_version"]["version_no"] == 2
    texts = {x["text"]: x["origin"] for x in r.json()["requirements"]}
    assert "Rust" not in texts and texts["Python"] == "extracted"
    assert c.get(f"{API}/job-descriptions/{jd_id}", params={"version": 1}).json()["requirements"]  # v1 intact


def test_the_rule_based_engine_is_recorded_so_a_later_model_change_marks_results_as_different(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    run_id = analyse(c, rv, jv).json()["id"]
    run_jobs()
    with session_scope() as db:
        assert db.execute(select(AnalysisRun.model_fingerprint)).scalar_one() == "rules"
        db.execute(text("UPDATE analysis_runs SET model_fingerprint = 'something-else'"))
    assert "analysis_method_changed" in c.get(f"{API}/analyses/{run_id}").json()["staleness"]["reasons"]


def test_check_constraint_blocks_partial_success(db_engine):
    uid, rid = uuid.uuid4(), uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=uid, email="x@example.com", password_hash="h"))
    with pytest.raises(Exception, match="ck_analysis_runs_results"):
        with session_scope() as db:
            db.execute(text("INSERT INTO resume_documents(id,user_id,title) VALUES (:d,:u,'t')"), {"d": rid, "u": uid})
            db.execute(text(
                "INSERT INTO resume_versions(id,document_id,user_id,version_no,source,status) "
                "VALUES (:v,:d,:u,1,'upload','ready')"), {"v": rid, "d": rid, "u": uid})
            db.execute(text("INSERT INTO job_descriptions(id,user_id,title) VALUES (:d,:u,'t')"), {"d": rid, "u": uid})
            db.execute(text(
                "INSERT INTO job_description_versions(id,job_id,user_id,version_no,source,raw_text) "
                "VALUES (:v,:d,:u,1,'paste','x')"), {"v": rid, "d": rid, "u": uid})
            db.execute(text(
                "INSERT INTO analysis_runs(id,user_id,resume_version_id,jd_version_id,status,pipeline_version) "
                "VALUES (:r,:u,:v,:v,'succeeded','p')"), {"r": rid, "u": uid, "v": rid})


def test_migrations_match_models(db_engine):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.models import Base

    with db_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations have drifted: {diff}"
    assert os.environ["TEST_DATABASE_URL"]
