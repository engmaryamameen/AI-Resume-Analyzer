"""HTTP-level contract tests that need no database (health, demo, middleware, auth guards).

Invariants: one stable error envelope; security headers on every response; cross-origin state
changes and oversized bodies are refused; protected routes never leak data to anonymous callers.
"""

import pytest

from app.demo import fixtures

API = "/api/v1"


def test_error_envelope_is_stable_for_unknown_routes(client):
    r = client.get("/nope")
    body = r.json()["error"]
    assert r.status_code == 404 and set(body) == {"code", "message", "details", "request_id"}
    assert body["request_id"] == r.headers["X-Request-ID"]


def test_security_headers_on_every_response(client):
    r = client.get("/healthz")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_client_supplied_request_id_is_only_echoed_when_well_formed(client):
    assert client.get("/healthz", headers={"X-Request-ID": "abc-12345678"}).headers["X-Request-ID"] == "abc-12345678"
    assert client.get("/healthz", headers={"X-Request-ID": "bad id\r\nX: y"}).headers["X-Request-ID"] != "bad id"


@pytest.mark.security
def test_cross_origin_state_change_is_rejected(client):
    r = client.post(f"{API}/auth/login", json={"email": "a@b.co", "password": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "origin_not_allowed"


@pytest.mark.security
def test_metrics_endpoint_is_disabled_without_a_token(client):
    assert client.get("/metrics").status_code == 404


@pytest.mark.security
@pytest.mark.parametrize("method,path", [
    ("get", "/resumes"), ("get", "/job-descriptions"), ("get", "/analyses"), ("get", "/auth/me"),
    ("get", "/admin/overview"),
    ("get", "/resumes/00000000-0000-0000-0000-000000000000"),
    ("get", "/analyses/00000000-0000-0000-0000-000000000000/report"),
])
def test_protected_routes_require_authentication(client, method, path):
    r = getattr(client, method)(API + path)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.security
def test_oversized_body_is_refused_before_processing(client):
    r = client.post(f"{API}/resumes", content=b"x" * (6 * 1024 * 1024 + 300_000),
                    headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


class TestDemo:
    def test_samples_are_synthetic_and_listed(self, client):
        body = client.get(f"{API}/demo/samples").json()
        assert {r["id"] for r in body["resumes"]} == {r.id for r in fixtures.RESUMES}
        assert "synthetic" in body["notice"].lower()

    def test_demo_analysis_needs_no_account_and_states_which_engine_ran(self, client):
        r = client.post(f"{API}/demo/analyze", json={"resume_id": "avery-backend", "job_id": "backend-platform"})
        assert r.status_code == 200
        body = r.json()
        assert body["engine"]["mode"] == "rules"
        assert {a["id"] for a in body["assessments"]} == {
            "requirement_evidence", "document_structure", "writing_style", "extraction_reliability"}
        by_name = {m["requirement"]["text"]: m for m in body["matches"]}
        assert by_name["Python"]["status"] == "supported"
        assert by_name["Kubernetes"]["status"] == "mentioned_only"      # listed, never shown in use
        assert by_name["Go"]["status"] == "no_evidence"

    def test_demo_results_carry_no_scores(self, client):
        r = client.post(f"{API}/demo/analyze", json={"resume_id": "avery-backend", "job_id": "backend-platform"})
        assert '"score"' not in r.text and '"band"' not in r.text
        assert all(m["probability"] is None for m in r.json()["matches"])

    def test_unstructured_resume_reports_uncertainty(self, client):
        body = client.post(f"{API}/demo/analyze", json={"resume_id": "sam-unstructured", "job_id": "backend-platform"}).json()
        codes = {u["code"] for u in body["resume"]["normalized"]["uncertainties"]}
        assert "no_sections_detected" in codes

    def test_custom_job_text_is_accepted_but_unknown_ids_are_not(self, client):
        ok = client.post(f"{API}/demo/analyze", json={"resume_id": "avery-backend",
              "job_text": "Requirements:\n- Experience with Python and PostgreSQL\n- Familiarity with Rust"})
        assert ok.status_code == 200
        assert client.post(f"{API}/demo/analyze", json={"resume_id": "x", "job_id": "backend-platform"}).status_code == 404
        assert client.post(f"{API}/demo/analyze", json={"resume_id": "avery-backend"}).status_code == 422

    def test_demo_is_rate_limited(self, client, monkeypatch):
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "rate_limit_demo_per_minute", 2)
        codes = [client.post(f"{API}/demo/analyze", json={"resume_id": "avery-backend", "job_id": "backend-platform"}).status_code
                 for _ in range(3)]
        assert codes == [200, 200, 429]


class TestModelStatus:
    def test_without_a_manifest_the_rule_based_reading_is_reported(self, client):
        body = client.get(f"{API}/system/models").json()
        assert body["learned_models_approved"] is False and body["models"] == [] and "rule-based" in body["note"]
