"""Section segmentation, contact fields, dates, experience estimate, parseability.

Invariants: blocks are verbatim text; unsure heuristics emit an Uncertainty instead of guessing;
an absent section is reported as absent, never fabricated.
"""

from datetime import date

import pytest

from app.documents.normalize import heading_kind, parse_date_range, union_months
from app.documents.parseability import assess
from app.documents.schema import DateRange
from tests.helpers import SAMPLE_RESUME, TODAY, build_doc


def kinds(doc):
    return [s.kind for s in doc.sections]


def test_sections_are_recognised_in_order():
    doc, _ = build_doc(SAMPLE_RESUME)
    assert kinds(doc) == ["header", "summary", "experience", "education", "skills"]


def test_blocks_reference_their_sections_and_keep_verbatim_text():
    doc, _ = build_doc(SAMPLE_RESUME)
    texts = {b.text for b in doc.blocks}
    assert "Built a billing API in Python and Django used by 30 internal teams" in texts
    assert all(b.section_id in {s.id for s in doc.sections} for b in doc.blocks)


def test_contact_fields_and_confidence():
    doc, _ = build_doc(SAMPLE_RESUME)
    assert doc.contact.email.value == "alex.tester@example.com"
    assert doc.contact.phone.value.replace(" ", "").startswith("+1555")
    assert doc.contact.name.value == "Alex Tester"
    assert doc.contact.name.confidence != "high"  # a guess must always ask for confirmation


def test_job_title_is_not_mistaken_for_a_name():
    doc, _ = build_doc("Senior Software Engineer\nSKILLS\nPython, Go\n")
    assert doc.contact.name.value is None
    assert any(u.code == "name_not_found" for u in doc.uncertainties)


def test_total_experience_from_dated_entries():
    doc, _ = build_doc(SAMPLE_RESUME)
    assert doc.total_experience_months == 73  # Jan 2020 .. Jan 2026 inclusive


def test_resume_without_experience_section_reports_absence():
    doc, _ = build_doc("Pat Student\npat@example.com\nEDUCATION\nBSc Biology, 2024\nSKILLS\nR, Python, Statistics\n")
    assert "experience" not in kinds(doc)
    assert doc.total_experience_months is None
    assert doc.entries == [] or all(e.date_range is None for e in doc.entries)


def test_resume_without_headings_is_flagged_not_guessed():
    doc, parse = build_doc("I built things.\nWrote tests.\nShipped code.\n")
    assert kinds(doc) == ["other"]
    assert any(u.code == "no_sections_detected" for u in doc.uncertainties)
    assert any(s.code == "no_sections_detected" for s in parse.signals)


def test_empty_extraction_is_an_error_not_an_empty_success():
    from app.documents.normalize import normalize

    doc = normalize([], None, today=TODAY)
    assert doc.uncertainties[0].severity == "error"
    assert assess([], doc).reliable_for_analysis is False


def test_scanned_style_document_is_marked_unreliable():
    doc, parse = build_doc("a\nb\nc\n")
    assert parse.reliable_for_analysis is False
    assert any(s.code == "little_text" and s.severity == "error" for s in parse.signals)


class TestDates:
    def test_month_precision(self):
        r = parse_date_range("Mar 2019 – Aug 2019", TODAY)
        assert (r.start, r.end, r.months, r.approximate) == ("2019-03", "2019-08", 6, False)

    def test_year_only_is_approximate(self):
        r = parse_date_range("2018 - 2020", TODAY)
        assert r.months == 36 and r.approximate

    def test_present_uses_supplied_clock(self):
        assert parse_date_range("Jan 2025 - Present", date(2025, 6, 15)).months == 6

    def test_reversed_range_is_rejected(self):
        assert parse_date_range("2021 - 2019", TODAY) is None

    def test_overlapping_ranges_are_not_double_counted(self):
        a = DateRange(start="2019-01", end="2020-12", months=24)
        b = DateRange(start="2020-06", end="2021-06", months=13)
        assert union_months([a, b], TODAY) == 30

    def test_separate_ranges_sum(self):
        a = DateRange(start="2019-01", end="2019-12", months=12)
        b = DateRange(start="2021-01", end="2021-06", months=6)
        assert union_months([a, b], TODAY) == 18


@pytest.mark.parametrize("line,kind", [
    ("EXPERIENCE", "experience"), ("Work Experience:", "experience"), ("Technical Skills", "skills"),
    ("Education & Training", "education"), ("Licenses and Certifications", "certifications"),
    ("Built an experience platform for retail", None),
])
def test_heading_detection(line, kind):
    assert heading_kind(line) == kind


def test_wrapped_bullet_lines_are_joined():
    doc, _ = build_doc(
        "SKILLS\nPython\nEXPERIENCE\nEngineer, Acme\n2020 - 2022\n- Built a service that processes\n"
        "large volumes of events every day\n")
    bullets = [b.text for b in doc.blocks if b.kind == "bullet"]
    assert bullets == ["Built a service that processes large volumes of events every day"]
