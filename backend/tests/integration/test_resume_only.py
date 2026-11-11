"""A résumé-only review is a real analysis, with no hidden/fabricated job description."""

import uuid
import pytest
from sqlalchemy import func, select

from app.analysis import service
from app.core.config import get_settings
from app.db.models import AnalysisRun, JobDescription, JobDescriptionVersion
from app.db.session import session_scope
from tests.integration.test_workflows import ready_resume, make_job, analyse
from tests.integration.test_guest import submit, complete

pytestmark = pytest.mark.integration


def test_resume_only_analysis_replay_and_all_exports(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    headers = {"Idempotency-Key": "resume-only-test-0001"}
    first = c.post("/api/v1/analyses", json={"resume_version_id": rv}, headers=headers)
    assert first.status_code == 202, first.text
    again = c.post(
        "/api/v1/analyses", json={"resume_version_id": rv, "jd_version_id": None}, headers=headers
    )
    assert first.json()["id"] == again.json()["id"]
    run_jobs()
    detail = c.get("/api/v1/analyses/" + first.json()["id"]).json()
    assert detail["status"] == "succeeded" and detail["jd_version_id"] is None
    assert detail["matches"] == [] and detail["review"] is None
    assert {a["id"] for a in detail["assessments"]} == {
        "document_structure",
        "writing_style",
        "extraction_reliability",
    }
    for format in ["json", "csv", "md"]:
        report = c.get(f"/api/v1/analyses/{first.json()['id']}/report?format={format}")
        assert report.status_code == 200, report.text
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(JobDescription)) == 0
        assert db.scalar(select(func.count()).select_from(JobDescriptionVersion)) == 0


def test_guest_resume_only_without_job_field(client, db_engine, run_jobs):
    from tests.integration.test_workflows import docx_file

    r = client.post(
        "/api/v1/guest/analyze",
        files=docx_file(),
        headers={"Origin": "http://localhost:3000", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 202, r.text
    result = complete(client, run_jobs)
    assert result.json()["status"] == "succeeded", result.text
    assert result.json()["report"]["jd_version_id"] is None
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(JobDescription)) == 0


def test_resume_only_comparison_and_cross_mode_rejection(make_user, run_jobs):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)

    def standalone(key):
        r = c.post(
            "/api/v1/analyses", json={"resume_version_id": rv}, headers={"Idempotency-Key": key}
        )
        assert r.status_code == 202, r.text
        run_jobs()
        return r.json()["id"]

    first, second = standalone("resume-only-base"), standalone("resume-only-target")
    compared = c.get(f"/api/v1/analyses/compare?base={first}&target={second}")
    assert compared.status_code == 200, compared.text
    _, jv = make_job(c)
    targeted = analyse(c, rv, jv)
    run_jobs()
    mixed = c.get(f"/api/v1/analyses/compare?base={first}&target={targeted.json()['id']}")
    assert mixed.status_code == 409 and mixed.json()["error"]["code"] == "review_modes_differ"


def test_failed_ai_review_fails_the_run_instead_of_faking_feedback(
    make_user, run_jobs, monkeypatch
):
    from app.core.errors import ServiceUnavailable

    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    monkeypatch.setattr(get_settings(), "reviewer_enabled", True)

    def unavailable(*args, **kwargs):
        raise ServiceUnavailable("Local model offline", code="ai_review_unavailable")

    monkeypatch.setattr(service, "review_document", unavailable)
    started = c.post("/api/v1/analyses", json={"resume_version_id": rv})
    run_jobs()
    result = c.get("/api/v1/analyses/" + started.json()["id"]).json()
    assert result["status"] == "failed" and result["error_code"] == "ai_review_unavailable"
    assert result["review"] is None and result["recommendations"] == []
