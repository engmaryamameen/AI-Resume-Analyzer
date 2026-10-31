"""Public demonstration endpoints: synthetic documents only, nothing stored.

The demo runs the rule-based reading, never learned models: those run in the worker for real accounts
and are not loaded into the web process. Results are labelled accordingly (`engine.mode == "rules"`).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.analysis.pipeline import analyze
from app.analysis.requirements import extract_requirements
from app.api.schemas import DemoAnalyzeIn
from app.core.config import Settings, get_settings
from app.core.errors import NotFound, ValidationFailed
from app.core.net import client_ip
from app.core.ratelimit import limiter
from app.demo import fixtures
from app.documents.isolated import RawLine
from app.documents.normalize import normalize
from app.documents.parseability import assess
from app.ml.engine import Budget
from app.ml.rules import RulesEngine

router = APIRouter(prefix="/demo", tags=["demo"])
_ENGINE = RulesEngine(notes=["The public demo always uses the rule-based reading."])
_DEMO_SECONDS = 10


@router.get("/samples")
def samples() -> dict[str, Any]:
    return {
        "resumes": [
            {"id": r.id, "title": r.title, "description": r.description} for r in fixtures.RESUMES
        ],
        "jobs": [
            {"id": j.id, "title": j.title, "description": j.description, "text": j.text}
            for j in fixtures.JOBS
        ],
        "notice": "All sample résumés are synthetic. Nothing you do here is stored.",
    }


@router.post("/analyze")
def demo_analyze(
    body: DemoAnalyzeIn, request: Request, settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    limiter.check(f"demo:{client_ip(request, settings)}", settings.rate_limit_demo_per_minute)
    resume = fixtures.get_resume(body.resume_id)
    if resume is None:
        raise NotFound("Unknown sample résumé.")
    job = fixtures.get_job(body.job_id) if body.job_id else None
    if body.job_id and job is None:
        raise NotFound("Unknown sample job description.")
    jd_text = job.text if job else (body.job_text or "").strip()
    if len(jd_text) < 40:
        raise ValidationFailed(
            "Choose a sample job or paste a job description of at least 40 characters.",
            code="jd_too_short",
        )

    requirements, jd_warnings = extract_requirements(jd_text)
    lines = [RawLine(text=t, page=1, bullet=False) for t in resume.text.splitlines() if t.strip()]
    document = normalize(lines, page_count=1)
    parse = assess([line.text for line in lines], document)
    result = analyze(document, parse, requirements, _ENGINE, lambda: Budget(_DEMO_SECONDS))
    by_ordinal = {r.ordinal: r for r in result.requirements}
    return {
        "resume": {
            "id": resume.id,
            "title": resume.title,
            "normalized": document.model_dump(mode="json"),
            "parseability": parse.model_dump(mode="json"),
        },
        "job": {
            "id": job.id if job else None,
            "title": job.title if job else "Pasted job description",
            "text": jd_text,
        },
        "engine": result.engine.model_dump(mode="json"),
        "assessments": [a.model_dump(mode="json") for a in result.assessments],
        "warnings": [w.model_dump(mode="json") for w in [*jd_warnings, *result.warnings]],
        "recommendations": [r.model_dump(mode="json") for r in result.recommendations],
        "limitations": result.limitations,
        "mentions": [m.model_dump(mode="json") for m in result.mentions],
        "matches": [
            {
                **m.model_dump(mode="json", exclude={"ordinal"}),
                "requirement": {
                    **by_ordinal[m.ordinal].model_dump(mode="json"),
                    "id": f"demo-{m.ordinal}",
                },
            }
            for m in result.matches
        ],
    }
