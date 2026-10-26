"""How far the extraction can be trusted. Descriptive: signals and a coarse level, not a quality score."""

from app.documents.schema import NormalizedDocument, Parseability, Uncertainty

# Each signal carries a weight; the level is a threshold on their sum. The weights are judgement calls,
# which is why only the coarse level (not the sum) is exposed.
_POOR_AT = 45
_FAIR_AT = 20
_UNRELIABLE_AT = 60


def assess(lines: list[str], doc: NormalizedDocument) -> Parseability:
    text = "\n".join(lines)
    pages = doc.page_count or 1
    signals: list[Uncertainty] = []
    weight = 0

    per_page = len(text) / pages
    if not text or per_page < 100:
        signals.append(Uncertainty(
            code="little_text", severity="error",
            message="Very little text was extracted. The file may be a scan or image-only; nothing was "
                    "guessed. Upload a text-based PDF or DOCX."))
        weight += _UNRELIABLE_AT
    elif per_page < 400:
        signals.append(Uncertainty(
            code="sparse_text", severity="warn", message="Less text than expected per page was extracted."))
        weight += 15

    visible = [c for c in text if not c.isspace()]
    if visible:
        if sum(c.isalpha() for c in visible) / len(visible) < 0.55:
            signals.append(Uncertainty(
                code="low_alphabetic_ratio", severity="warn",
                message="The extracted text contains many symbols or digits; encoding or font problems are possible."))
            weight += 15
        if text.count("\N{REPLACEMENT CHARACTER}") / len(text) > 0.005:
            signals.append(Uncertainty(
                code="encoding_issues", severity="warn", message="Unreadable characters were found in the text."))
            weight += 15

    if len(lines) > 20 and sum(len(line) for line in lines) / len(lines) < 14:
        signals.append(Uncertainty(
            code="possible_multicolumn_order", severity="warn",
            message="Lines are unusually short; a multi-column or table layout may have scrambled reading order."))
        weight += 15

    if not any(s.kind not in {"header", "other"} for s in doc.sections):
        signals.append(Uncertainty(
            code="no_sections_detected", severity="warn", message="No standard section headings were recognised."))
        weight += 20
    if not doc.contact.email.value and not doc.contact.phone.value:
        signals.append(Uncertainty(
            code="no_contact_details", severity="info", message="No email or phone number was detected."))
        weight += 5

    level = "poor" if weight >= _POOR_AT else "fair" if weight >= _FAIR_AT else "good"
    has_error = any(s.severity == "error" for s in signals)
    return Parseability(level=level, reliable_for_analysis=not has_error and weight < _UNRELIABLE_AT, signals=signals)
