"""Report assembly. Every output is built defensively because reports contain user-controlled text.

- CSV: cells beginning with = + - @ TAB or CR are prefixed so spreadsheets never evaluate them.
- Markdown: HTML-significant characters are escaped; links are never generated from content.
- All formats: contact details are removed from every text field; downloads are attachments (nosniff).
"""

import csv
import io
import json
import re

from app.core.logging import redact
from app.core.textclean import strip_controls
from app.db.models import AnalysisRun

_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+!|<>~])")
_DISCLAIMER = (
    "Generated from the wording of a résumé and a job description by locally executed analysis. It describes "
    "what the résumé's text claims; it does not verify those claims or predict hiring outcomes."
)


def csv_safe(value: object) -> str:
    text = strip_controls("" if value is None else str(value), keep_whitespace=False)
    return "'" + text if text.startswith(_FORMULA_PREFIX) else text


def md_safe(value: object) -> str:
    text = strip_controls("" if value is None else str(value), keep_whitespace=False).replace("&", "&amp;")
    return _MD_SPECIAL.sub(r"\\\1", text)


def clean(text: str | None, limit: int = 400) -> str:
    return redact(text or "")[:limit]


def build_report(*, run: AnalysisRun, staleness: dict, requirements: list[dict], matches: list[dict]) -> dict:
    by_requirement = {m["requirement_id"]: m for m in matches}
    rows = []
    for r in requirements:
        m = by_requirement.get(r["id"])
        rows.append({
            "requirement": clean(r["text"], 500), "kind": r["kind"], "category": r["category"], "origin": r["origin"],
            "status": m["status"] if m else None, "conflict": bool(m and m["conflict"]),
            "probability": m["probability"] if m else None, "reasons": [clean(x) for x in (m["reasons"] if m else [])],
            "explanation": clean(m["explanation"]) if m else None,
            "evidence": [{"excerpt": clean(e["excerpt"]), "section": e.get("section_kind"), "label": e.get("label"),
                          "roles": e.get("roles", []), "derived": e.get("derived", False)}
                         for e in (m["evidence"] if m else [])],
        })
    summary = run.summary or {}
    return {
        "report_version": 2, "disclaimer": _DISCLAIMER,
        "analysis": {"id": str(run.id), "created_at": run.created_at.isoformat(), "pipeline_version": run.pipeline_version,
                     "engine": run.engine, "staleness": staleness,
                     "assessments": run.assessments or [], "warnings": run.warnings or [],
                     "limitations": summary.get("limitations", [])},
        "requirements": rows,
        "recommendations": [{"kind": r["kind"], "title": clean(r["title"]), "detail": clean(r["detail"]),
                             "excerpt": clean(r.get("excerpt"))} for r in summary.get("recommendations", [])],
    }


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, default=str)


def to_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["requirement", "kind", "category", "origin", "status", "conflict", "calibrated_probability",
                     "explanation", "first_evidence_excerpt"])
    for r in report["requirements"]:
        first = r["evidence"][0]["excerpt"] if r["evidence"] else ""
        writer.writerow([csv_safe(x) for x in (r["requirement"], r["kind"], r["category"], r["origin"], r["status"],
                                               r["conflict"], r["probability"], r["explanation"], first)])
    return buffer.getvalue()


def to_markdown(report: dict) -> str:
    analysis = report["analysis"]
    engine = analysis.get("engine") or {}
    lines = ["# Résumé analysis report", "", md_safe(report["disclaimer"]), "",
             f"Engine: {md_safe(engine.get('mode', 'unknown'))}", ""]
    for assessment in analysis["assessments"]:
        lines += [f"## {md_safe(assessment['label'])}", md_safe(assessment["summary"]), ""]
        lines += [f"- {md_safe(m['name'].replace('_', ' '))}: {md_safe(m['value'])}" for m in assessment["metrics"]]
        lines.append("")
    if analysis["warnings"]:
        lines += ["## Warnings", ""] + [f"- {md_safe(w['message'])}" for w in analysis["warnings"]] + [""]
    lines += ["## Requirements and evidence", ""]
    for r in report["requirements"]:
        lines.append(f"### {md_safe(r['requirement'])}")
        lines.append(f"{md_safe(r['kind'])} · {md_safe(r['category'])} · status: **{md_safe(r['status'])}**"
                     + (" · conflicting evidence" if r["conflict"] else ""))
        lines += [f"- Evidence ({md_safe(e['label'] or 'derived')}): \"{md_safe(e['excerpt'])}\"" for e in r["evidence"]]
        if r["explanation"]:
            lines.append(f"- {md_safe(r['explanation'])}")
        lines.append("")
    if report["recommendations"]:
        lines += ["## Recommendations", ""]
        lines += [f"- **{md_safe(x['title'])}** {md_safe(x['detail'])}" for x in report["recommendations"]]
        lines.append("")
    lines += ["## Limitations", ""] + [f"- {md_safe(x)}" for x in analysis["limitations"]]
    return "\n".join(lines) + "\n"
