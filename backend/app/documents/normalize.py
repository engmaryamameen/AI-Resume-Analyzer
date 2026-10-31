"""Raw extracted lines -> NormalizedDocument (sections, blocks, entries, contact details, dates).

Deterministic structure parsing. It never invents text: every block is the extracted text of one or
more consecutive lines. Facts derived from block text (entries, date ranges, total experience) are
computed in `derive_structure`, which is also re-run after a user edits blocks, so edits cannot leave
derived data stale. Interpreting what the text *means* (skills, degrees, evidence) is the ML pipeline's
job, not this module's.
"""

import re
from datetime import date

from app.documents.isolated import RawLine
from app.documents.schema import (
    Block,
    Contact,
    ContactField,
    DateRange,
    Entry,
    NormalizedDocument,
    Section,
    SectionKind,
    Uncertainty,
)

SECTION_ALIASES: dict[SectionKind, tuple[str, ...]] = {
    "summary": (
        "summary",
        "professional summary",
        "profile",
        "about me",
        "objective",
        "career objective",
        "personal statement",
        "executive summary",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "internships",
        "internship experience",
        "relevant experience",
    ),
    "education": (
        "education",
        "academic background",
        "education and training",
        "academic qualifications",
    ),
    "projects": (
        "projects",
        "personal projects",
        "selected projects",
        "academic projects",
        "open source",
        "open source projects",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "key skills",
        "technologies",
        "tech stack",
        "competencies",
        "tools and technologies",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "licenses",
        "licenses and certifications",
        "courses",
        "training",
    ),
    "awards": ("awards", "honors", "honours", "achievements", "accomplishments"),
    "publications": ("publications", "talks"),
    "volunteering": ("volunteering", "volunteer experience", "community"),
    "languages": ("languages",),
    "interests": ("interests", "hobbies"),
}
_HEADING_LOOKUP = {alias: kind for kind, aliases in SECTION_ALIASES.items() for alias in aliases}

_BULLET = re.compile(r"^\s*(?:[•·▪▫◦‣●○■□➢➤►\-–—*]|\d{1,2}[.)])\s+")
_MONTHS = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE = rf"(?:(?:{_MONTHS})\.?\s+)?(?:19|20)\d{{2}}|\d{{1,2}}/(?:19|20)\d{{2}}"
_RANGE = re.compile(
    rf"(?P<s>{_DATE})\s*(?:-|–|—|to)\s*(?P<e>present|current|now|ongoing|{_DATE})", re.IGNORECASE
)
_MONTH_NUM = {
    name: i
    for i, name in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_PRESENT = {"present", "current", "now", "ongoing"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<![\w/])(\+?\d[\d\s().-]{7,}\d)(?![\w/])")
_LINK = re.compile(
    r"(?:https?://[^\s,;|]+|(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com)/[^\s,;|]+)", re.I
)
_TITLE_WORDS = {
    "engineer",
    "developer",
    "manager",
    "analyst",
    "designer",
    "resume",
    "curriculum",
    "vitae",
    "consultant",
    "specialist",
    "architect",
    "scientist",
    "intern",
    "lead",
    "director",
}
_WRAP_MIN_LINE = (
    45  # a line this long that doesn't end a sentence was probably wrapped by the page width
)
_DERIVED_UNCERTAINTIES = {"experience_dates_missing", "date_precision_low"}


def heading_kind(line: str) -> SectionKind | None:
    cleaned = re.sub(r"[^A-Za-z& ]", " ", line).replace("&", " and ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    if not cleaned or len(line) > 45:
        return None
    return _HEADING_LOOKUP.get(cleaned)


def _parse_point(token: str, *, is_end: bool, today: date) -> tuple[int, int, bool]:
    t = token.strip().lower()
    if t in _PRESENT:
        return today.year, today.month, False
    slash = re.match(r"(\d{1,2})/((?:19|20)\d{2})", t)
    if slash:
        return int(slash.group(2)), min(max(int(slash.group(1)), 1), 12), False
    year_match = re.search(r"(?:19|20)\d{2}", t)
    assert year_match is not None  # guaranteed by the _DATE pattern that produced the token
    year = int(year_match.group(0))
    month = _MONTH_NUM.get(t[:3])
    if month is not None and t[:1].isalpha():
        return year, month, False
    return year, (12 if is_end else 1), True


def parse_date_range(text: str, today: date) -> DateRange | None:
    m = _RANGE.search(text)
    if not m:
        return None
    sy, sm, start_approx = _parse_point(m.group("s"), is_end=False, today=today)
    ey, em, end_approx = _parse_point(m.group("e"), is_end=True, today=today)
    if (ey, em) < (sy, sm) or ey > today.year + 1:
        return None
    return DateRange(
        start=f"{sy:04d}-{sm:02d}",
        end="present" if m.group("e").lower() in _PRESENT else f"{ey:04d}-{em:02d}",
        months=(ey - sy) * 12 + (em - sm) + 1,
        approximate=start_approx or end_approx,
    )


def union_months(ranges: list[DateRange], today: date) -> int:
    """Total months covered by the ranges, counting overlapping periods once."""
    spans = []
    for r in ranges:
        sy, sm = map(int, r.start.split("-"))
        ey, em = (today.year, today.month) if r.end == "present" else map(int, r.end.split("-"))
        spans.append((sy * 12 + sm, ey * 12 + em))
    spans.sort()
    total = 0
    current: tuple[int, int] | None = None
    for start, end in spans:
        if current is None or start > current[1] + 1:
            if current is not None:
                total += current[1] - current[0] + 1
            current = (start, end)
        else:
            current = (current[0], max(current[1], end))
    if current is not None:
        total += current[1] - current[0] + 1
    return total


def derive_structure(doc: NormalizedDocument, today: date) -> NormalizedDocument:
    """Recompute entries, total experience and their uncertainties from the current block text."""
    blocks = doc.block_map()
    entries: list[Entry] = []
    for section in doc.sections:
        entry: Entry | None = None
        for block_id in section.block_ids:
            block = blocks[block_id]
            if block.kind == "entry_header":
                date_range = parse_date_range(block.text, today)
                if (
                    entry is not None
                    and not entry.block_ids
                    and entry.date_range is None
                    and date_range
                ):
                    entry.date_range = date_range  # the date sits on a second header line
                    entry.block_ids.append(block_id)
                else:
                    entry = Entry(
                        id=f"e{len(entries) + 1}",
                        section_id=section.id,
                        header_block_id=block_id,
                        date_range=date_range,
                    )
                    entries.append(entry)
            elif entry is not None:
                entry.block_ids.append(block_id)

    kind_of = doc.section_kind_by_id()
    ranges = [
        e.date_range
        for e in entries
        if e.date_range and kind_of.get(e.section_id) in {"experience", "volunteering"}
    ]
    notes = [u for u in doc.uncertainties if u.code not in _DERIVED_UNCERTAINTIES]
    months: int | None = None
    if ranges:
        months = union_months(ranges, today)
        if any(r.approximate for r in ranges):
            notes.append(
                Uncertainty(
                    code="date_precision_low",
                    severity="info",
                    message="Some dates have no month, so the experience estimate is approximate.",
                )
            )
    elif "experience" in kind_of.values():
        notes.append(
            Uncertainty(
                code="experience_dates_missing",
                severity="info",
                message="Experience entries were found but no parseable date ranges, so total "
                "experience cannot be estimated.",
            )
        )
    return doc.model_copy(
        update={"entries": entries, "total_experience_months": months, "uncertainties": notes}
    )


def normalize(
    lines: list[RawLine], page_count: int | None, today: date | None = None
) -> NormalizedDocument:
    today = today or date.today()
    doc = NormalizedDocument(page_count=page_count)
    if not lines:
        doc.uncertainties.append(
            Uncertainty(code="no_text", message="No text was extracted.", severity="error")
        )
        return doc

    counters = {"b": 0, "s": 0}

    def next_id(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}{counters[prefix]}"

    section = Section(id=next_id("s"), kind="header")
    doc.sections.append(section)
    saw_heading = False
    previous_length = 0
    previous_kind: str | None = None

    for line_no, raw in enumerate(lines, start=1):
        text = re.sub(r"\s+", " ", raw.text).strip()
        if not text:
            continue
        is_bullet = raw.bullet or bool(_BULLET.match(text))
        heading = None if is_bullet else heading_kind(text)
        if heading:
            saw_heading = True
            section = Section(id=next_id("s"), kind=heading, heading=text)
            doc.sections.append(section)
            previous_kind = None
            continue

        if is_bullet:
            text = _BULLET.sub("", text, count=1)
        last = doc.blocks[-1] if doc.blocks and doc.blocks[-1].section_id == section.id else None
        has_range = parse_date_range(text, today) is not None

        wrapped = (
            last is not None
            and section.kind != "header"
            and not is_bullet
            and not has_range
            and previous_kind in {"bullet", "paragraph"}
            and (previous_length >= _WRAP_MIN_LINE or previous_kind == "bullet")
            and last.text[-1:] not in ".;:!?"
        )
        if wrapped and last is not None:
            last.text = f"{last.text} {text}"[:4000]
            previous_length = len(text)
            continue

        if is_bullet:
            kind = "bullet"
        elif section.kind in {"experience", "projects", "education", "volunteering"} and (
            has_range
            or (len(text) <= 90 and text[-1:] not in ".;!?" and previous_kind != "entry_header")
        ):
            kind = "entry_header"
        else:
            kind = "paragraph"
        block = Block(
            id=next_id("b"),
            section_id=section.id,
            kind=kind,
            text=text[:4000],
            page=raw.page,
            line=line_no,
        )
        doc.blocks.append(block)
        section.block_ids.append(block.id)
        previous_kind, previous_length = kind, len(text)

    if not saw_heading:
        doc.sections[0].kind = "other"
        doc.uncertainties.append(
            Uncertainty(
                code="no_sections_detected",
                severity="warn",
                message="No section headings were recognised, so content could not be assigned to "
                "experience, education or skills.",
            )
        )

    _extract_contact(doc)
    return derive_structure(doc, today)


def _extract_contact(doc: NormalizedDocument) -> None:
    header_ids: set[str] = set()
    for s in doc.sections:
        if s.kind in {"header", "other"}:
            header_ids.update(s.block_ids[:15])
    candidates = [b for b in doc.blocks if b.id in header_ids] or doc.blocks[:10]
    contact = Contact()
    for b in candidates:
        if not contact.email.value and (m := _EMAIL.search(b.text)):
            contact.email = ContactField(value=m.group(0), confidence="high", block_id=b.id)
        if not contact.phone.value:
            for m in _PHONE.finditer(b.text):
                digits = re.sub(r"\D", "", m.group(1))
                if 8 <= len(digits) <= 15 and not re.fullmatch(
                    r"(?:19|20)\d{2}(?:19|20)\d{2}", digits
                ):
                    contact.phone = ContactField(
                        value=m.group(1).strip(), confidence="medium", block_id=b.id
                    )
                    break
        for m in _LINK.finditer(b.text):
            url = m.group(0).rstrip(".,)")
            if url not in contact.links and len(contact.links) < 6:
                contact.links.append(url)
    for index, b in enumerate(candidates[:6]):
        tokens = b.text.split()
        if not 2 <= len(tokens) <= 4 or _EMAIL.search(b.text) or re.search(r"\d", b.text):
            continue
        if any(t.lower().strip(".,") in _TITLE_WORDS for t in tokens):
            continue
        if all(re.fullmatch(r"[A-Za-z][A-Za-z'.\-]*", t) and t[0].isupper() for t in tokens):
            contact.name = ContactField(
                value=b.text, confidence="medium" if index == 0 else "low", block_id=b.id
            )
            break
    doc.contact = contact
    if not contact.name.value:
        doc.uncertainties.append(
            Uncertainty(
                code="name_not_found",
                severity="info",
                message="A candidate name could not be identified; please enter it.",
            )
        )
    elif contact.name.confidence != "high":
        doc.uncertainties.append(
            Uncertainty(
                code="name_unverified",
                severity="info",
                block_id=contact.name.block_id,
                message="The name is a best guess; please confirm it.",
            )
        )
    if not contact.email.value:
        doc.uncertainties.append(
            Uncertainty(
                code="email_not_found", severity="info", message="No email address was found."
            )
        )
