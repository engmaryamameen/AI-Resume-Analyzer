"""Compare two completed analyses and say whether the comparison is like-for-like."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.service import get_run
from app.core.errors import Conflict
from app.db.models import JobDescriptionVersion, JobRequirement, RequirementMatch, ResumeVersion

_RANK = {
    "no_evidence": 0,
    "insufficient": 1,
    "contradicted": 1,
    "mentioned_only": 2,
    "supported": 3,
}
_NUMERIC_UNITS = {"count", "percent", "months"}


def _key(requirement: JobRequirement) -> str:
    if requirement.category in {"skill", "soft_skill"} and requirement.terms:
        return f"{requirement.category}:{requirement.terms[0]}"
    return f"{requirement.category}:{' '.join(requirement.text_.lower().split())[:120]}"


def _statuses(db: Session, run_id: uuid.UUID) -> dict[str, tuple[str, JobRequirement]]:
    rows = db.execute(
        select(RequirementMatch, JobRequirement)
        .join(JobRequirement, JobRequirement.id == RequirementMatch.requirement_id)
        .where(RequirementMatch.run_id == run_id)
    ).all()
    return {_key(r): (m.status, r) for m, r in rows}


def _metrics(assessments: list[dict[str, Any]] | None) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (a["id"], m["name"]): m
        for a in assessments or []
        for m in a["metrics"]
        if m["unit"] in _NUMERIC_UNITS
    }


def compare_runs(
    db: Session, user_id: uuid.UUID, base_id: uuid.UUID, target_id: uuid.UUID
) -> dict[str, Any]:
    base, target = get_run(db, user_id, base_id), get_run(db, user_id, target_id)
    if base.status != "succeeded" or target.status != "succeeded":
        raise Conflict(
            "Both analyses must have completed successfully.", code="analysis_not_complete"
        )

    notes: list[dict[str, Any]] = []
    if (base.pipeline_version, base.model_fingerprint) != (
        target.pipeline_version,
        target.model_fingerprint,
    ):
        notes.append(
            {
                "code": "different_analysis_method",
                "message": "These analyses used different models or rules, so differences may reflect the "
                "method as well as the résumé.",
            }
        )
    jobs = {
        rid: db.get(JobDescriptionVersion, rid)
        for rid in (base.jd_version_id, target.jd_version_id)
    }
    if jobs[base.jd_version_id].job_id != jobs[target.jd_version_id].job_id:  # type: ignore[union-attr]
        notes.append(
            {
                "code": "different_job_descriptions",
                "message": "These analyses target different job descriptions; differences reflect the "
                "postings as much as the résumé.",
            }
        )
    elif base.jd_version_id != target.jd_version_id:
        notes.append(
            {
                "code": "job_description_version_differs",
                "message": "The requirement list was edited between these analyses.",
            }
        )
    resumes = {
        rid: db.get(ResumeVersion, rid)
        for rid in (base.resume_version_id, target.resume_version_id)
    }
    if resumes[base.resume_version_id].document_id != resumes[target.resume_version_id].document_id:  # type: ignore[union-attr]
        notes.append(
            {"code": "different_resumes", "message": "These analyses use different résumés."}
        )

    base_metrics, target_metrics = _metrics(base.assessments), _metrics(target.assessments)
    metric_changes = [
        {
            "assessment": a,
            "name": n,
            "unit": m["unit"],
            "before": base_metrics[(a, n)]["value"] if (a, n) in base_metrics else None,
            "after": m["value"],
        }
        for (a, n), m in target_metrics.items()
    ]

    before, after = _statuses(db, base.id), _statuses(db, target.id)
    changes: list[dict[str, str | None]] = []
    for key in sorted(set(before) | set(after)):
        b, t = before.get(key), after.get(key)
        if b and t:
            change = (
                "improved"
                if _RANK[t[0]] > _RANK[b[0]]
                else "weaker"
                if _RANK[t[0]] < _RANK[b[0]]
                else "unchanged"
            )
            changes.append(
                {"requirement": t[1].text_, "before": b[0], "after": t[0], "change": change}
            )
        elif t:
            changes.append(
                {"requirement": t[1].text_, "before": None, "after": t[0], "change": "added"}
            )
        elif b:
            changes.append(
                {"requirement": b[1].text_, "before": b[0], "after": None, "change": "removed"}
            )
    return {
        "base_id": str(base.id),
        "target_id": str(target.id),
        "like_for_like": not notes,
        "notes": notes,
        "metric_changes": metric_changes,
        "requirement_changes": changes,
    }
