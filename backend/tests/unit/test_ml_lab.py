"""The ML lab's torch-free parts: dataset schema, validation, splitting, synthetic data and metrics.

Anything that needs a model or a GPU (encoding, training, calibration, benchmarking) is not covered here:
those need real weights and are run by a person (docs/local-models.md).
"""

from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.ml.rules import RulesEngine
from ml import metrics, split, synth
from ml.evaluate import build_report
from ml.inputs import query_of
from ml.schema import ExtractionRecord, Requirement, VerificationRecord, parse_markup, parse_record, read_jsonl
from ml.validate import check_records, check_splits

CHALLENGE = sorted((REPO_ROOT / "ml" / "data" / "challenge").glob("*.jsonl"))


class TestMarkup:
    def test_spans_point_at_the_plain_text(self):
        text, spans = parse_markup("Built [[Kafka|SKILL|affirmed]] pipelines at [[Acme|ORG]].")
        assert text == "Built Kafka pipelines at Acme."
        assert [(text[s.start: s.end], s.type, s.role) for s in spans] == [("Kafka", "SKILL", "affirmed"), ("Acme", "ORG", None)]

    def test_text_without_markup_has_no_spans(self):
        assert parse_markup("Plain text.") == ("Plain text.", [])

    @pytest.mark.parametrize("marked", ["[[x|NOPE|affirmed]]", "[[x|SKILL|maybe]]", "[[x|SKILL]]", "[[x|ORG|affirmed]]"])
    def test_invalid_markup_is_rejected(self, marked):
        with pytest.raises(ValueError):
            parse_markup(marked)

    def test_records_may_be_authored_with_markup(self):
        record = parse_record({"kind": "extraction", "id": "a", "group": "g", "source": "hand_written",
                               "section_kind": "skills", "marked": "[[Go|SKILL|listed]]"})
        assert isinstance(record, ExtractionRecord) and record.text == "Go" and record.spans[0].end == 2

    def test_unknown_record_kind_is_rejected(self):
        with pytest.raises(ValueError):
            parse_record({"kind": "other"})


class TestChallengeSets:
    def test_every_file_parses_and_validates(self):
        records = [r for path in CHALLENGE for r in read_jsonl(path)]
        report = check_records(records)
        assert records and report.ok, report.errors

    def test_challenge_data_is_hand_written_and_never_in_a_training_split(self):
        assert {r.source for path in CHALLENGE for r in read_jsonl(path)} == {"hand_written"}

    def test_every_verdict_is_represented(self):
        labels = {r.label for path in CHALLENGE for r in read_jsonl(path) if isinstance(r, VerificationRecord)}
        assert labels == {"supports", "mentions_only", "contradicts", "insufficient", "unrelated"}


class TestValidation:
    def record(self, **overrides):
        base = {"kind": "extraction", "id": "r1", "group": "g", "source": "synthetic", "section_kind": "experience",
                "text": "Built Python services", "spans": [{"start": 6, "end": 12, "type": "SKILL", "role": "affirmed"}]}
        return parse_record({**base, **overrides})

    def test_a_correct_record_passes(self):
        assert check_records([self.record()]).ok

    def test_span_outside_the_text_is_an_error(self):
        spans = [{"start": 6, "end": 99, "type": "SKILL", "role": "affirmed"}]
        assert not check_records([self.record(spans=spans)]).ok

    def test_overlapping_spans_are_an_error(self):
        spans = [{"start": 6, "end": 12, "type": "SKILL", "role": "affirmed"}, {"start": 8, "end": 14, "type": "ORG"}]
        assert not check_records([self.record(spans=spans)]).ok

    def test_duplicate_ids_are_an_error(self):
        assert not check_records([self.record(), self.record()]).ok

    def test_skill_roles_are_required_and_other_types_take_none(self):
        with pytest.raises(ValueError):
            self.record(spans=[{"start": 6, "end": 12, "type": "SKILL"}])
        with pytest.raises(ValueError):
            self.record(spans=[{"start": 6, "end": 12, "type": "ORG", "role": "affirmed"}])

    def test_requirement_names_must_be_canonical(self):
        wrong = parse_record({"kind": "verification", "id": "v", "group": "g", "source": "hand_written",
                              "section_kind": "experience", "text": "Ran k8s", "label": "supports",
                              "requirement": {"type": "skill", "value": "k8s"}})
        assert not check_records([wrong]).ok

    def test_leakage_across_splits_is_detected(self, tmp_path):
        from ml.schema import write_jsonl

        shared = self.record(id="a")
        write_jsonl(tmp_path / "train.t-extraction.jsonl", [shared])
        write_jsonl(tmp_path / "test.t-extraction.jsonl", [self.record(id="b", group="other")])
        report = check_splits(tmp_path)
        assert any("identical text" in e for e in report.errors)

    def test_a_group_in_two_splits_is_detected(self, tmp_path):
        from ml.schema import write_jsonl

        write_jsonl(tmp_path / "train.t-extraction.jsonl", [self.record(id="a")])
        write_jsonl(tmp_path / "test.t-extraction.jsonl", [self.record(id="b", text="Ran Go jobs", spans=[])])
        assert any("several splits" in e for e in check_splits(tmp_path).errors)


class TestSplit:
    def test_assignment_depends_only_on_group_and_seed(self):
        assert split.assign("family-1", 13) == split.assign("family-1", 13)
        assert {split.assign(f"family-{i}", 13) for i in range(200)} == {"train", "validation", "calibration", "test"}

    def test_fractions_are_roughly_respected(self):
        counts = {}
        for i in range(4000):
            counts[split.assign(f"g{i}", 3)] = counts.get(split.assign(f"g{i}", 3), 0) + 1
        assert 0.65 < counts["train"] / 4000 < 0.75 and 0.07 < counts["test"] / 4000 < 0.13


class TestSyntheticData:
    def test_generation_is_deterministic(self):
        first, second = synth.generate(2, 7, 13), synth.generate(2, 7, 13)
        assert [r.model_dump() for r in first] == [r.model_dump() for r in second]

    def test_a_different_seed_gives_different_data(self):
        assert [r.model_dump() for r in synth.generate(2, 7, 13)] != [r.model_dump() for r in synth.generate(2, 8, 13)]

    def test_generated_records_are_valid_and_cover_every_label_and_tag(self):
        records = synth.generate(2, 7, 13)
        report = check_records(records)
        assert report.ok, report.errors[:5]
        labels = {r.label for r in records if isinstance(r, VerificationRecord)}
        tags = {t for r in records for t in r.tags}
        assert labels == {"supports", "mentions_only", "contradicts", "insufficient", "unrelated"}
        assert {"negation", "hedge", "degree_ambiguity", "paraphrase", "hard_negative"} <= tags

    def test_splits_of_generated_data_have_no_leakage(self, tmp_path):
        records = synth.generate(2, 7, 13)
        split.write_splits(records, tmp_path, seed=13, prefix="syn")
        report = check_splits(tmp_path)
        assert report.ok, report.errors[:5]
        assert split.load_split(tmp_path, "train", "extraction")

    def test_synthetic_text_never_reaches_the_challenge_sets(self):
        challenge = {" ".join(t.lower().split()) for path in CHALLENGE for r in read_jsonl(path)
                     for t in ([r.text] if hasattr(r, "text") else [p.text for p in r.passages])}
        generated = {" ".join(r.text.lower().split()) for r in synth.generate(3, 7, 13) if hasattr(r, "text")}
        assert not challenge & generated


class TestMetrics:
    def test_precision_recall_f1(self):
        m = metrics.prf(tp=6, fp=2, fn=4)
        assert m["precision"] == 0.75 and m["recall"] == 0.6 and m["f1"] == pytest.approx(2 * 0.75 * 0.6 / 1.35)

    def test_zero_denominators_do_not_divide(self):
        assert metrics.prf(0, 0, 0)["f1"] == 0.0

    def test_exact_span_scores_count_type_mismatches_as_errors(self):
        gold = [{(0, 5, "SKILL"), (10, 14, "ORG")}]
        predicted = [{(0, 5, "SKILL"), (10, 14, "TITLE")}]
        scores = metrics.span_scores(gold, predicted)
        assert scores["micro"]["tp"] == 1 and scores["micro"]["fp"] == 1 and scores["micro"]["fn"] == 1
        assert scores["SKILL"]["f1"] == 1.0 and scores["ORG"]["recall"] == 0.0

    def test_confusion_matrix_rows_are_gold_labels(self):
        report = metrics.classification_report([("a", "a"), ("a", "b"), ("b", "b")], ["a", "b"])
        assert report["confusion"] == {"a": {"a": 1, "b": 1}, "b": {"a": 0, "b": 1}}
        assert report["accuracy"] == pytest.approx(2 / 3)

    def test_macro_f1_ignores_labels_absent_from_the_gold_data(self):
        report = metrics.classification_report([("a", "a")], ["a", "b"])
        assert report["macro_f1"] == 1.0

    def test_retrieval_scores(self):
        scores = metrics.retrieval_scores([[False, True, False], [True], [False, False]])
        assert scores["hit@1"] == pytest.approx(1 / 3) and scores["hit@3"] == pytest.approx(2 / 3)
        assert scores["mrr"] == pytest.approx((0.5 + 1.0 + 0.0) / 3)

    def test_percentile_interpolates(self):
        assert metrics.percentile([1, 2, 3, 4], 0.5) == 2.5


class TestEvaluationHarness:
    @pytest.fixture(scope="class")
    def report(self):
        return build_report(RulesEngine(), CHALLENGE)

    def test_report_names_its_engine_and_data(self, report):
        assert report["engine"]["mode"] == "rules"
        assert len(report["data"]["digest"]) == 64 and report["data"]["sources"] == {"hand_written": report["data"]["records"]}

    def test_retrieval_and_verification_are_reported_separately(self, report):
        assert {"hit@1", "mrr"} <= set(report["retrieval"])
        assert {"macro_f1", "false_support_rate", "confusion"} <= set(report["verification"])

    def test_extraction_is_reported_per_type_and_per_challenge_tag(self, report):
        assert "micro" in report["extraction"]["spans"]
        assert {"degree_ambiguity", "negation", "hedge", "layout"} <= set(report["extraction"]["spans_by_tag"])

    def test_the_rule_based_engine_reports_no_probabilities(self, report):
        assert "ece" not in report["verification"] and "role_ece" not in report["extraction"]

    def test_the_report_is_reproducible(self, report):
        assert build_report(RulesEngine(), CHALLENGE)["data"]["digest"] == report["data"]["digest"]


def test_query_hypothesis_comes_from_the_record_so_training_and_inference_agree():
    requirement = Requirement(type="skill", value="Kubernetes")
    query = query_of(requirement, "q")
    assert query.hypothesis == requirement.hypothesis() and query.term_ids == ["kubernetes"]


def test_repository_layout_the_lab_depends_on():
    assert (Path(REPO_ROOT) / "ml" / "data" / "challenge").is_dir() and (Path(REPO_ROOT) / "models" / "manifest.json").is_file()
