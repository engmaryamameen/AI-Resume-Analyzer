"""The rule-based baseline engine. It is not machine learning; these tests pin down what it claims."""

import pytest

from app.analysis.passages import build_passages
from app.ml.contracts import Passage, Query
from app.ml.engine import Budget, BudgetExceeded
from app.ml.rules import RulesEngine
from tests.helpers import SAMPLE_RESUME, build_doc

ENGINE = RulesEngine()


def passage(text, section="experience", pid="p1"):
    return Passage(id=pid, text=text, context=section, section_kind=section)


def mentions(text, section="experience"):
    return {(m.text, m.type): m.role for m in ENGINE.extract([passage(text, section)], Budget(5))}


def query(term, name):
    return Query(id="q", retrieval_query=name, hypothesis=f"The candidate has hands-on experience with {name}.",
                 term_ids=[term], surface_forms=[name])


def test_engine_describes_itself_as_the_rule_based_reading():
    assert ENGINE.info.mode == "rules" and ENGINE.info.fingerprint == "rules" and not ENGINE.info.calibrated


class TestRoles:
    def test_skill_used_in_a_sentence_is_affirmed(self):
        assert mentions("Built internal APIs in Python for the billing team")[("Python", "SKILL")] == "affirmed"

    def test_skill_in_a_list_is_listed(self):
        assert mentions("Skills: Python, Docker", "skills")[("Python", "SKILL")] == "listed"

    @pytest.mark.parametrize("text", [
        "No professional experience with Kubernetes.",
        "Have never used Kubernetes in production.",
        "Unfamiliar with Kubernetes.",
    ])
    def test_negation_is_recognised(self, text):
        assert mentions(text)[("Kubernetes", "SKILL")] == "negated"

    @pytest.mark.parametrize("text", ["Currently learning Docker.", "Basic familiarity with Docker.", "Exploring Docker for a side project."])
    def test_hedging_is_recognised(self, text):
        assert mentions(text)[("Docker", "SKILL")] == "hedged"

    def test_negation_does_not_leak_across_clauses(self):
        found = mentions("No experience with Scala, but built services in Python.")
        assert found[("Scala", "SKILL")] == "negated" and found[("Python", "SKILL")] == "affirmed"


class TestDegrees:
    def test_state_abbreviation_and_office_suite_are_not_degrees(self):
        assert not [k for k in mentions("Moved to Boston, MA and administered MS Office for staff") if k[1] == "DEGREE"]

    def test_degree_in_education_is_found(self):
        assert mentions("MS in Statistics, Summit College", "education")[("MS", "DEGREE")] == "affirmed"

    def test_unfinished_degree_is_negated_and_pursued_degree_is_hedged(self):
        assert mentions("Left the PhD programme before finishing", "education")[("PhD", "DEGREE")] == "negated"
        assert mentions("Pursuing an MBA at Summit College", "education")[("MBA", "DEGREE")] == "hedged"


class TestRetrievalAndVerification:
    def test_bm25_ranks_the_passage_with_the_query_terms_first(self):
        passages = [passage("Organised the newsletter", pid="a"), passage("Ran Kubernetes clusters", pid="b")]
        found = ENGINE.retrieve([query("kubernetes", "Kubernetes")], passages, 2, Budget(5))["q"]
        assert [c.passage_id for c in found] == ["b"] and found[0].method == "bm25"

    def test_affirmed_mention_supports_negated_contradicts_listed_mentions_only(self):
        pairs = [(query("python", "Python"), passage(t, s)) for t, s in [
            ("Built services in Python", "experience"), ("No experience with Python", "experience"),
            ("Skills: Python, Go", "skills"), ("Currently learning Python", "experience")]]
        labels = [v.label for v in ENGINE.verify(pairs, Budget(5))]
        assert labels == ["supports", "contradicts", "mentions_only", "insufficient"]

    def test_unrelated_passage_is_unrelated_and_no_probabilities_are_reported(self):
        verdict = ENGINE.verify([(query("python", "Python"), passage("Organised the newsletter"))], Budget(5))[0]
        assert verdict.label == "unrelated" and verdict.probs is None and verdict.source == "rules"

    def test_budget_is_enforced(self):
        with pytest.raises(BudgetExceeded):
            ENGINE.extract([passage("Python")], Budget(-1))


def test_passages_follow_the_document_and_skip_the_contact_header():
    doc, _ = build_doc(SAMPLE_RESUME)
    passages = build_passages(doc)
    assert all(p.section_kind != "header" for p in passages)
    bullet = next(p for p in passages if p.text.startswith("Built a billing API"))
    assert bullet.section_kind == "experience" and "Backend Engineer" in bullet.context
