"""Export safety, log redaction, private storage.

Invariants: spreadsheet formulas never survive export; contact details never reach logs or reports;
storage keys are random and cannot escape the storage root.
"""

import json
import logging
import os
import stat
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.logging import _JsonFormatter, redact
from app.documents.storage import LocalPrivateStore
from app.reports.builder import build_report, clean, csv_safe, md_safe, to_csv, to_json, to_markdown


def _run():
    return SimpleNamespace(
        id="run-1", created_at=datetime(2026, 1, 1, tzinfo=UTC), pipeline_version="pipeline-2",
        engine={"mode": "rules"}, warnings=[], assessments=[{
            "id": "requirement_evidence", "label": "Requirements and evidence", "summary": "s",
            "metrics": [{"name": "supported", "value": 1, "unit": "count", "definition": "d"}]}],
        summary={"limitations": ["x"], "recommendations": [
            {"kind": "add_evidence", "title": "+bad", "detail": "Mail a@b.com", "excerpt": "@excerpt"}]})


def _report(requirement="=cmd|' /C calc'!A0"):
    reqs = [{"id": "1", "text": requirement, "kind": "required", "category": "skill", "origin": "extracted"}]
    matches = [{"requirement_id": "1", "status": "supported", "conflict": False, "probability": None, "reasons": [],
                "evidence": [{"excerpt": "mail a@b.com", "section_kind": "experience", "label": "supports"}],
                "explanation": "+bad"}]
    return build_report(run=_run(), staleness={"is_stale": False, "reasons": []}, requirements=reqs, matches=matches)


@pytest.mark.security
class TestExportSafety:
    @pytest.mark.parametrize("cell", ["=HYPERLINK(\"http://evil\")", "+1+1", "-2+3", "@SUM(A1)"])
    def test_formula_prefixes_are_neutralised(self, cell):
        assert csv_safe(cell).startswith("'")

    def test_control_characters_are_removed_before_the_formula_check(self):
        assert csv_safe("\tcmd") == "cmd" and csv_safe("a" + chr(0x202E) + "b") == "ab"

    def test_ordinary_values_are_unchanged(self):
        assert csv_safe("Python developer") == "Python developer" and csv_safe(None) == ""

    def test_markdown_escapes_html_and_links(self):
        out = md_safe("<script>alert(1)</script> [x](http://evil) & more")
        assert "<" not in out.replace("\\<", "") and "](" not in out.replace("\\]\\(", "")

    def test_text_fields_drop_contact_details(self):
        assert clean("Reach me at jane@example.com or +1 555 010 0100") == "Reach me at [email] or [phone]"

    def test_csv_export_neutralises_every_text_column(self):
        csv_text = to_csv(_report())
        row = csv_text.splitlines()[1]
        assert "'=cmd" in row and "'+bad" in row and "a@b.com" not in csv_text

    def test_json_and_markdown_exports_exclude_raw_contact_details(self):
        report = _report("Python")
        for rendered in (to_json(report), to_markdown(report)):
            assert "a@b.com" not in rendered
        assert json.loads(to_json(report))["report_version"] == 2

    def test_recommendations_are_cleaned_too(self):
        report = _report("Python")
        assert report["recommendations"][0]["detail"] == "Mail [email]"

    def test_disclaimer_says_it_does_not_verify_claims_or_predict_outcomes(self):
        assert "does not verify" in _report()["disclaimer"]

    def test_markdown_states_the_engine_that_produced_the_analysis(self):
        assert "Engine: rules" in to_markdown(_report("Python"))


@pytest.mark.security
class TestLogRedaction:
    def _format(self, msg, **extra):
        rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), None)
        rec.__dict__.update(extra)
        return json.loads(_JsonFormatter().format(rec))

    def test_message_text_is_redacted(self):
        out = self._format("user jane@example.com phoned +1 555 010 0100 with token=abc123secret")
        blob = json.dumps(out)
        assert "jane@example.com" not in blob and "555" not in blob and "abc123secret" not in blob

    @pytest.mark.parametrize("key", ["text", "content", "prompt", "email", "excerpt", "password", "authorization"])
    def test_sensitive_fields_are_withheld(self, key):
        assert self._format("event", **{key: "résumé body or secret"})[key] == "[withheld]"

    def test_non_scalar_extras_are_omitted(self):
        assert self._format("event", payload={"cv": "body"})["payload"] == "[omitted]"

    def test_redact_helper(self):
        assert redact("Authorization: Bearer abc.def") .endswith("[redacted]")


class TestPrivateStorage:
    def test_keys_are_random_hex_and_files_are_private(self, tmp_path):
        store = LocalPrivateStore(tmp_path / "s")
        k1, k2 = store.put(b"a"), store.put(b"a")
        assert k1 != k2 and len(k1) == 32 and int(k1, 16) >= 0
        assert stat.S_IMODE(os.stat(store.path(k1)).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(store.root).st_mode) == 0o700

    @pytest.mark.security
    @pytest.mark.parametrize("key", ["../../etc/passwd", "a" * 31, "g" * 32, "/etc/passwd", "..", ""])
    def test_traversal_and_malformed_keys_are_rejected(self, tmp_path, key):
        store = LocalPrivateStore(tmp_path / "s")
        with pytest.raises(ValueError):
            store.path(key)

    def test_delete_is_idempotent_and_ignores_bad_keys(self, tmp_path):
        store = LocalPrivateStore(tmp_path / "s")
        k = store.put(b"x")
        store.delete(k)
        store.delete(k)
        store.delete("../nope")
        assert not store.path(k).exists()
