"""Turning a job posting into requirements.

Invariants: every requirement keeps a span into the posting; benefits and company blurbs are not
requirements; a stronger cue upgrades a preferred skill; inferred requirements are marked as inferred;
"MS Office" is never read as a master's degree.
"""

from app.analysis.requirements import extract_requirements


def extract(text):
    return extract_requirements(text)[0]


def by_term(requirements, term):
    return [r for r in requirements if term in r.terms and r.category in {"skill", "soft_skill"}]


def test_skills_under_a_requirements_heading_are_required():
    reqs = extract("Requirements\n- Experience with Python and PostgreSQL\n")
    assert {r.text for r in reqs if r.origin == "extracted" and r.category == "skill"} == {"Python", "PostgreSQL"}
    assert all(r.kind == "required" for r in reqs if r.origin == "extracted")


def test_skills_under_a_nice_to_have_heading_are_preferred():
    assert by_term(extract("Nice to have\n- Experience with Terraform\n"), "terraform")[0].kind == "preferred"


def test_a_required_mention_upgrades_an_earlier_preferred_one_without_duplicating():
    reqs = by_term(extract("Nice to have\n- Experience with Docker\nRequirements\n- Strong Docker skills\n"), "docker")
    assert len(reqs) == 1 and reqs[0].kind == "required"


def test_years_of_experience_are_captured_as_a_requirement():
    reqs = [r for r in extract("Requirements\n- 5+ years of professional software engineering experience\n")
            if r.category == "experience_years"]
    assert len(reqs) == 1 and reqs[0].min_years == 5


def test_degree_requirement_is_recognised():
    reqs = [r for r in extract("Requirements\n- A bachelor's degree is required\n") if r.category == "education"]
    assert reqs and reqs[0].terms[0] == "degree:bachelor"


def test_ms_office_is_not_a_masters_degree():
    reqs = extract("Requirements\n- Proficiency in MS Office is required\n")
    assert not [r for r in reqs if r.category == "education"]


def test_benefits_and_company_text_are_not_requirements():
    reqs = extract("About us\nWe use Python and offer flexible hours.\n\nBenefits\n- Experience with free lunch and Docker\n")
    assert [r for r in reqs if r.origin == "extracted"] == []


def test_alternatives_share_a_group():
    reqs = by_term(extract("Requirements\n- Experience with Python or Java\n"), "python")
    assert reqs[0].source_span["alt_group"] is not None


def test_every_extracted_requirement_points_back_into_the_posting():
    text = "Requirements\n- Experience with Python and PostgreSQL\n- 3 years of experience in backend development\n"
    for r in extract(text):
        if r.origin == "extracted":
            assert 0 <= r.source_span["start"] < r.source_span["end"] <= len(text)


def test_inferred_requirements_are_marked_and_say_why():
    inferred = [r for r in extract("Requirements\n- Experience with PostgreSQL\n") if r.origin == "inferred"]
    assert inferred and all(r.kind == "preferred" and r.source_span["reason"] for r in inferred)


def test_empty_posting_reports_that_nothing_was_found():
    reqs, warnings = extract_requirements("Welcome to our company page.")
    assert reqs == [] and warnings[0].code == "no_requirements_found"
