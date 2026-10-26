"""The decision table and probability calibration. Pure functions: no models, no database.

Invariants: the weaker of two readings wins; explicit negation outranks a mention; supporting and
contradicting passages together are a conflict, never support; a probability appears only when a calibrated
estimate exists and the two signals agree.
"""

import math

import pytest

from app.ml.calibration import (
    brier_score,
    expected_calibration_error,
    fit_temperature,
    softmax,
)
from app.ml.contracts import Verdict
from app.ml.decision import CandidateEvidence, combine, decide, role_label


def evidence(label, roles=(), probs=None, pid="p1", score=None):
    return CandidateEvidence(pid, Verdict(label=label, probs=probs, source="learned"), tuple(roles), score)


class TestDecisionTable:
    def test_no_candidates_means_no_evidence(self):
        assert decide([]).status == "no_evidence"

    def test_only_unrelated_passages_mean_no_evidence(self):
        assert decide([evidence("unrelated"), evidence("unrelated", pid="p2")]).status == "no_evidence"

    def test_agreement_stands_and_carries_the_probability(self):
        d = decide([evidence("supports", ["affirmed"], probs={"supports": 0.91, "mentions_only": 0.09})])
        assert d.status == "supported" and d.probability == pytest.approx(0.91) and not d.conflict

    def test_no_probability_without_a_calibrated_estimate(self):
        assert decide([evidence("supports", ["affirmed"])]).probability is None

    def test_verifier_support_but_listed_only_is_mentioned_only(self):
        d = decide([evidence("supports", ["listed"], probs={"supports": 0.9})])
        assert d.status == "mentioned_only"
        assert d.probability is None  # the two signals disagreed, so no single probability applies
        assert any("differently" in r for r in d.reasons)

    def test_explicit_negation_outranks_a_mention(self):
        assert combine("mentions_only", "contradicts") == ("contradicts", False)

    def test_negated_mention_makes_an_unrelated_passage_contradict(self):
        assert decide([evidence("unrelated", ["negated"])]).status == "contradicted"

    def test_hedged_mention_is_insufficient_not_support(self):
        assert decide([evidence("supports", ["hedged"])]).status == "insufficient"

    def test_supporting_and_contradicting_passages_conflict(self):
        d = decide([evidence("supports", ["affirmed"]), evidence("contradicts", ["negated"], pid="p2")])
        assert d.conflict and d.status == "insufficient"
        assert any("supports and contradicts" in r for r in d.reasons)

    def test_support_in_one_passage_beats_a_mention_in_another(self):
        d = decide([evidence("mentions_only", ["listed"]), evidence("supports", ["affirmed"], pid="p2")])
        assert d.status == "supported" and d.evidence[0].candidate.passage_id == "p2"

    def test_stronger_retrieval_score_orders_equal_labels(self):
        d = decide([evidence("supports", ["affirmed"], pid="a", score=0.2), evidence("supports", ["affirmed"], pid="b", score=0.9)])
        assert [j.candidate.passage_id for j in d.evidence] == ["b", "a"]

    def test_one_label_per_passage_from_several_mentions(self):
        assert role_label(["listed", "affirmed"]) == "supports"
        assert role_label(["listed", "negated"]) == "contradicts"
        assert role_label([]) is None

    @pytest.mark.parametrize("a", ["supports", "mentions_only", "contradicts", "insufficient"])
    @pytest.mark.parametrize("b", ["supports", "mentions_only", "contradicts", "insufficient"])
    def test_every_pair_of_labels_has_a_defined_result(self, a, b):
        label, agreed = combine(a, b)
        assert label in {"supports", "mentions_only", "contradicts", "insufficient"}
        assert agreed == (a == b)
        assert combine(a, b)[0] == combine(b, a)[0]  # the table does not depend on which signal came first


class TestCalibration:
    def test_softmax_is_a_distribution_and_temperature_flattens_it(self):
        sharp, flat = softmax([4.0, 0.0, 0.0]), softmax([4.0, 0.0, 0.0], temperature=4.0)
        assert sum(sharp) == pytest.approx(1.0) and max(flat) < max(sharp)

    def test_softmax_survives_large_logits(self):
        assert all(math.isfinite(p) for p in softmax([1000.0, 0.0]))

    def test_overconfident_model_gets_a_temperature_above_one(self):
        rows = [[4.0, 0.0]] * 8
        assert fit_temperature(rows, [0, 0, 0, 0, 1, 1, 1, 1]) > 1.5

    def test_underconfident_model_gets_a_temperature_below_one(self):
        assert fit_temperature([[0.3, 0.0]] * 8, [0] * 8) < 1.0

    def test_ece_of_a_confident_wrong_model_is_large(self):
        assert expected_calibration_error([[1.0, 0.0]] * 4, [0, 0, 1, 1]) == pytest.approx(0.5)

    def test_ece_of_a_calibrated_model_is_near_zero(self):
        rows = [[0.9, 0.1]] * 10
        assert expected_calibration_error(rows, [0] * 9 + [1]) == pytest.approx(0.0, abs=1e-9)

    def test_brier_score_is_zero_for_perfect_predictions(self):
        assert brier_score([[1.0, 0.0], [0.0, 1.0]], [0, 1]) == 0.0
