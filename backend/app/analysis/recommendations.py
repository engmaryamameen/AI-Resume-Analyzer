"""Recommendations anchored in the résumé's own text.

Nothing here is generated prose. Each recommendation points at a verbatim excerpt (or at the absence of
one) and says what the evidence status implies. `fill_in` is a blank for the user to complete with true
facts; it is labelled as such in the interface and is never presented as model output.
"""

from collections.abc import Sequence

from app.analysis.schema import MatchResult, Recommendation, RequirementDraft
from app.documents.schema import NormalizedDocument
from app.lang.text import weak_opener

MAX_RECOMMENDATIONS = 25
MAX_STYLE_NOTES = 6


def build_recommendations(
    doc: NormalizedDocument, requirements: Sequence[RequirementDraft], matches: Sequence[MatchResult]
) -> list[Recommendation]:
    ordered = sorted(zip(requirements, matches, strict=True), key=lambda p: (p[0].kind != "required", p[0].ordinal))
    out: list[Recommendation] = []
    for requirement, match in ordered:
        if requirement.origin == "inferred":
            continue
        anchor = next((e for e in match.evidence if e.block_id), None)
        name = requirement.text
        if match.status == "mentioned_only":
            out.append(Recommendation(
                kind="add_evidence", requirement_ordinal=requirement.ordinal, title=f"Show how you used “{name}”",
                detail="It is named but not described. If it is accurate, say what you built or changed with it, "
                       "in the role or project where you used it.",
                block_id=anchor.block_id if anchor else None, excerpt=anchor.excerpt if anchor else None,
                fill_in="[what you did] with [skill], [result you can verify]"))
        elif match.status == "contradicted":
            out.append(Recommendation(
                kind="resolve_conflict", requirement_ordinal=requirement.ordinal, title=f"Check what the résumé says about “{name}”",
                detail="Text in the résumé contradicts this requirement. If it is out of date or wrong, correct it.",
                block_id=anchor.block_id if anchor else None, excerpt=anchor.excerpt if anchor else None))
        elif match.status == "insufficient" and anchor is not None:
            out.append(Recommendation(
                kind="clarify", requirement_ordinal=requirement.ordinal, title=f"Make “{name}” specific",
                detail=match.explanation or "The related text isn't specific enough to count as evidence.",
                block_id=anchor.block_id, excerpt=anchor.excerpt))
    if doc.total_experience_months is None and any(s.kind == "experience" for s in doc.sections):
        out.append(Recommendation(
            kind="add_dates", title="Add a date range to each role",
            detail="No role has a date range the reader could parse, so total experience can't be worked out. "
                   "Use a form like “Jan 2021 – Present”."))
    kinds = doc.section_kind_by_id()
    notes = [b for b in doc.blocks if b.kind == "bullet" and kinds.get(b.section_id) in {"experience", "projects", "other"}
             and weak_opener(b.text)][:MAX_STYLE_NOTES]
    out += [Recommendation(
        kind="style_note", title="Start with what you did",
        detail=f"This bullet opens with “{weak_opener(b.text)}”, which says little about your own contribution.",
        block_id=b.id, excerpt=b.text[:400]) for b in notes]
    return out[:MAX_RECOMMENDATIONS]
