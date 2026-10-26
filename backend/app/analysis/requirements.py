"""Job description -> explicit requirements, plus clearly marked inferred ones.

Rule-based parsing of the posting's structure (headings, bullets, cues). Every requirement keeps a
character span into the original text so the user can see where it came from and correct it.
Interpreting the résumé against these requirements is the ML pipeline's job (analysis.evidence).
"""

import re
from dataclasses import dataclass

from app.analysis.schema import AnalysisWarning, RequirementDraft
from app.lang.taxonomy import Taxonomy, TermHit, get_taxonomy
from app.ml.degree import degree_level, find_degrees

MAX_REQUIREMENTS = 60
MAX_INFERRED = 8

_BULLET = re.compile(r"^\s*(?:[•·▪◦‣●○■*\-–—]|\d{1,2}[.)])\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

_HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ignore": ("benefits", "perks", "about us", "about the company", "who we are", "compensation",
               "salary", "equal opportunity", "our culture", "how to apply", "what we offer",
               "why join", "about the team", "our mission"),
    "preferred": ("nice to have", "preferred", "bonus", "good to have", "desired", "ideal",
                  "extra credit", "a plus"),
    "required": ("requirements", "qualifications", "what you'll need", "what you bring", "must have",
                 "minimum", "basic qualifications", "who you are", "you have", "you'll need",
                 "what we're looking for", "skills and experience", "required"),
    "responsibility": ("responsibilities", "what you'll do", "what you will do", "the role",
                       "day to day", "day-to-day", "you will", "your impact", "in this role"),
}
_PREFERRED_CUE = re.compile(
    r"\b(nice to have|preferred|a plus|is a plus|bonus|ideally|desirable|desired|good to have|"
    r"an advantage|would be (?:great|a plus))\b", re.I)
_REQUIRED_CUE = re.compile(r"\b(must|required|requires|minimum|mandatory|essential|need to|needs to)\b", re.I)
_REQUIREMENT_CUE = re.compile(
    r"\b(must|required|requires?|experience (?:with|in|using|of)|proficien\w+|knowledge of|"
    r"familiar\w*|ability to|degree|certif\w+|expertise|skilled|background in|hands-on|"
    r"strong|understanding of)\b", re.I)
# Years only count as a requirement when they qualify experience ("5+ years of experience", "experience: 3 years").
_YEARS = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\b[^.]{0,60}?\b(?:experience|background|exposure)\b"
    r"|\b(?:experience|background)\b[^.]{0,40}?(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)
_CERT = re.compile(
    r"\b(certif\w+|pmp|cissp|cka|ckad|aws certified|azure certified|google cloud certified|scrum master|"
    r"security\+)\b", re.I)
_ALTERNATIVE_GAP = re.compile(r"\bor\b|and/or|^\s*/\s*$", re.I)
_EQUIVALENT = re.compile(r"\b(or )?(equivalent|related field|relevant experience)\b", re.I)


@dataclass
class _Line:
    start: int
    text: str


def _lines(raw: str) -> list[_Line]:
    return [_Line(m.start(), m.group(0)) for m in re.finditer(r"[^\n]+", raw) if m.group(0).strip()]


def _header_context(text: str, taxonomy: Taxonomy) -> str | None:
    stripped = text.strip()
    if _BULLET.match(stripped) or len(stripped) > 70 or re.search(r"\d", stripped) or taxonomy.find(stripped):
        return None  # a line with a number or a named skill is a requirement, not a heading
    lowered = stripped.lower().rstrip(":").strip()
    exact = any(lowered == k for keys in _HEADER_KEYWORDS.values() for k in keys)
    if not (stripped.endswith(":") or stripped.isupper() or exact or (len(lowered.split()) <= 4 and stripped.istitle())):
        return None
    for context in ("ignore", "preferred", "required", "responsibility"):
        if any(k in lowered for k in _HEADER_KEYWORDS[context]):
            return context
    return None


def _kind_for(sentence: str, context: str | None) -> str | None:
    if _PREFERRED_CUE.search(sentence):
        return "preferred"
    if _REQUIRED_CUE.search(sentence) or context == "required":
        return "required"
    if context in {"preferred", "responsibility"}:
        return "preferred"
    return "required" if _REQUIREMENT_CUE.search(sentence) or _YEARS.search(sentence) else None


def _is_alternative(sentence: str, hits: list[TermHit]) -> bool:
    """True when the skills in the sentence are alternatives ("Python, Go, or Java"), not all required."""
    ordered = sorted(hits, key=lambda h: h.start)
    return any(_ALTERNATIVE_GAP.search(sentence[a.end:b.start]) for a, b in zip(ordered, ordered[1:]))


def extract_requirements(
    jd_text: str, taxonomy: Taxonomy | None = None
) -> tuple[list[RequirementDraft], list[AnalysisWarning]]:
    tax = taxonomy or get_taxonomy()
    requirements: list[RequirementDraft] = []
    seen: dict[str, RequirementDraft] = {}
    context: str | None = None
    alternative_groups = 0

    def add(**fields) -> RequirementDraft:  # noqa: ANN003
        requirement = RequirementDraft(ordinal=len(requirements), **fields)
        requirements.append(requirement)
        return requirement

    for line in _lines(jd_text):
        header = _header_context(line.text, tax)
        if header:
            context = header
            continue
        if context == "ignore":
            continue
        body = _BULLET.sub("", line.text, count=1)
        body_start = line.start + len(line.text) - len(body)
        pieces = [(0, len(body))] if body != line.text else _sentence_spans(body)
        for start, end in pieces:
            sentence = body[start:end].strip()
            if len(sentence.split()) < 2 or len(requirements) >= MAX_REQUIREMENTS:
                continue
            kind = _kind_for(sentence, context)
            if kind is None:
                continue
            span = {"start": body_start + start, "end": body_start + end}
            hits = tax.find(sentence)
            term_ids = list(dict.fromkeys(h.term_id for h in hits))
            skill_hits = [h for h in hits if tax.get(h.term_id).category != "soft"]
            group = None
            if len(skill_hits) >= 2 and _is_alternative(sentence, skill_hits):
                alternative_groups += 1
                group = alternative_groups

            years = _YEARS.search(sentence)
            if years:
                number = float(years.group(1) or years.group(2))
                add(text=_trim(sentence), kind=kind, category="experience_years", terms=term_ids,
                    min_years=number, source_span=span)
            markers = education_markers(sentence)
            if markers and not skill_hits and not years:
                add(text=_trim(sentence), kind=kind, category="education", terms=markers, source_span=span)
            elif _CERT.search(sentence) and not skill_hits:
                add(text=_trim(sentence), kind=kind, category="certification", source_span=span,
                    terms=certification_terms(sentence))

            for term_id in term_ids:
                if term_id in seen:
                    if kind == "required" and seen[term_id].kind == "preferred" and group is None:
                        seen[term_id].kind = "required"
                    continue
                term = tax.get(term_id)
                seen[term_id] = add(
                    text=term.name, kind=kind, category="soft_skill" if term.category == "soft" else "skill",
                    terms=[term_id], source_span={**span, "alt_group": group})

            if context == "responsibility" and len(sentence.split()) >= 4 and not years:
                add(text=_trim(sentence), kind="preferred", category="responsibility", terms=term_ids,
                    source_span=span)

    warnings = []
    if len(requirements) >= MAX_REQUIREMENTS:
        warnings.append(AnalysisWarning(
            code="requirements_truncated", severity="info",
            message=f"Only the first {MAX_REQUIREMENTS} requirements were kept."))
    requirements.extend(_inferred(seen, tax, start_ordinal=len(requirements)))
    if not any(r.origin == "extracted" for r in requirements):
        warnings.append(AnalysisWarning(
            code="no_requirements_found",
            message="No requirements could be identified. Paste the full posting, or add requirements manually."))
    return requirements, warnings


def education_markers(sentence: str) -> list[str]:
    """["degree:<level>", "equivalent_ok"?] for a sentence that asks for a degree, else []."""
    degrees = find_degrees(sentence, "other")
    if not degrees and not re.search(r"\bdegree\b", sentence, re.I):
        return []
    level = degree_level(sentence[degrees[0].start:degrees[0].end]) if degrees else None
    return [f"degree:{level or 'bachelor'}"] + (["equivalent_ok"] if _EQUIVALENT.search(sentence) else [])


def certification_terms(sentence: str) -> list[str]:
    return [m.group(0).lower() for m in _CERT.finditer(sentence)][:4]


def _inferred(seen: dict[str, RequirementDraft], tax: Taxonomy, start_ordinal: int) -> list[RequirementDraft]:
    implied_by: dict[str, list[str]] = {}
    for term_id in seen:
        for implied in tax.implied_by(term_id):
            if implied not in seen:
                implied_by.setdefault(implied, []).append(term_id)
    out: list[RequirementDraft] = []
    for implied, sources in sorted(implied_by.items())[:MAX_INFERRED]:
        names = ", ".join(tax.get(s).name for s in sources[:3])
        out.append(RequirementDraft(
            ordinal=start_ordinal + len(out), text=tax.get(implied).name, kind="preferred",
            category="soft_skill" if tax.get(implied).category == "soft" else "skill", origin="inferred",
            terms=[implied], source_span={"inferred_from": sources, "reason": f"implied by {names}"}))
    return out


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENTENCE_BREAK.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return spans


def _trim(text: str, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
