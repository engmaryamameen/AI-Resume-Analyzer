"""Degree recognition and levels.

`degree_level` maps the text of a mention that has already been identified as a degree to a level.
`find_degrees` is the rule-based detector used by the rules engine: unlike a bare pattern match it
looks at the context of ambiguous abbreviations (MA, MS, BA, BS), so "Boston, MA" and "MS Office" are
not degrees. The learned extractor replaces this detector when available.
"""

import re
from dataclasses import dataclass

LEVELS = ("associate", "bachelor", "master", "doctorate")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS, start=1)}

_WORD_FORMS = re.compile(
    r"\b(?:ph\.?\s?d\.?|doctorate|doctor of [a-z]+|master(?:'s|s)?(?: of| in| degree)?|"
    r"bachelor(?:'s|s)?(?: of| in| degree)?|associate(?:'s)?(?: degree| of)|mba|b\.?\s?eng\.?|m\.?\s?eng\.?|"
    r"b\.?\s?sc\.?|m\.?\s?sc\.?|btech|mtech|b\.tech|m\.tech)\b",
    re.IGNORECASE,
)
_PERIOD_ABBREVIATIONS = re.compile(r"\b(?:B\.S\.|B\.A\.|M\.S\.|M\.A\.)")
_BARE_ABBREVIATION = re.compile(r"\b(BS|BA|MS|MA)\b")
_MICROSOFT_PRODUCTS = re.compile(
    r"^\s*(?:office|excel|word|powerpoint|project|access|teams|outlook|sql|azure|dynamics|visio|sharepoint)\b",
    re.IGNORECASE,
)
_FOLLOWED_BY_FIELD = re.compile(r"^\s*(?:in|of|\()\s*[A-Za-z]", re.IGNORECASE)
_DEGREE_INTRO = re.compile(
    r"(?:earned|completed|holds?|with|a|an|my|received|obtained|awarded)\s*$", re.IGNORECASE
)
_STATE_CONTEXT = re.compile(r",\s*$")


@dataclass(frozen=True)
class DegreeSpan:
    start: int
    end: int


def degree_level(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bph\.?\s?d\b|\bdoctor", t):
        return "doctorate"
    if re.search(r"\bmaster|\bm\.?\s?sc\b|\bmba\b|\bm\.?\s?eng\b|\bm\.?\s?tech\b|\bm\.?[sa]\b", t):
        return "master"
    if re.search(r"\bbachelor|\bb\.?\s?sc\b|\bb\.?\s?eng\b|\bb\.?\s?tech\b|\bb\.?[sa]\b", t):
        return "bachelor"
    if re.search(r"\bassociate", t):
        return "associate"
    return None


def find_degrees(text: str, section_kind: str) -> list[DegreeSpan]:
    spans = [DegreeSpan(m.start(), m.end()) for m in _WORD_FORMS.finditer(text)]
    spans += [DegreeSpan(m.start(), m.end()) for m in _PERIOD_ABBREVIATIONS.finditer(text)]
    for m in _BARE_ABBREVIATION.finditer(text):
        before, after = text[: m.start()], text[m.end() :]
        if _STATE_CONTEXT.search(before) and not _FOLLOWED_BY_FIELD.match(after):
            continue  # "Boston, MA"
        if m.group(1) == "MS" and _MICROSOFT_PRODUCTS.match(after):
            continue  # "MS Office"
        starts_entry = section_kind == "education" and len(before.strip()) <= 2
        if starts_entry or _FOLLOWED_BY_FIELD.match(after) or _DEGREE_INTRO.search(before):
            spans.append(DegreeSpan(m.start(), m.end()))
    return _without_overlaps(spans)


def _without_overlaps(spans: list[DegreeSpan]) -> list[DegreeSpan]:
    kept: list[DegreeSpan] = []
    for span in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if not kept or span.start >= kept[-1].end:
            kept.append(span)
    return kept
