"""Evaluate an inference engine on labelled records and write a JSON report.

    python -m ml.evaluate --engine rules --data ml/data/challenge/*.jsonl --out ml/runs/rules-challenge.json
    python -m ml.evaluate --candidate ml/runs/<run> --data <test split files> --out report.json

Retrieval and verification are measured separately: retrieval is judged on whether the relevant passage is
ranked highly, verification on the verdict it gives for a passage that is already in front of it.
Every number in a report comes from the files named in it; nothing is carried over from earlier runs.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from app.ml.calibration import expected_calibration_error
from app.ml.contracts import ROLE_TYPES, ROLES, VERDICT_LABELS, Passage
from app.ml.engine import Budget, Engine

from ml.inputs import passage_of, query_of
from ml.metrics import (
    classification_report,
    label_counts,
    rate,
    retrieval_scores,
    span_scores,
)
from ml.schema import (
    ExtractionRecord,
    Record,
    Requirement,
    RetrievalRecord,
    VerificationRecord,
    dataset_digest,
    read_jsonl,
)

NO_TIME_LIMIT = 10**9
MAX_LISTED_ERRORS = (
    200  # record ids only: no text, so a report about private data stays free of it
)


def _budget() -> Budget:
    return Budget(NO_TIME_LIMIT)


def evaluate_extraction(engine: Engine, records: Sequence[ExtractionRecord]) -> dict:
    if not records:
        return {}
    passages = [passage_of(r) for r in records]
    started = time.perf_counter()
    mentions = engine.extract(passages, _budget())
    seconds = time.perf_counter() - started
    by_passage: dict[str, list] = defaultdict(list)
    for mention in mentions:
        by_passage[mention.passage_id].append(mention)

    gold_sets, predicted_sets = [], []
    role_pairs: list[tuple[str, str]] = []
    role_probs, role_labels = [], []
    per_tag_pairs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record in records:
        found = by_passage.get(record.id, [])
        gold = {(s.start, s.end, s.type) for s in record.spans}
        predicted = {(m.start, m.end, m.type) for m in found}
        gold_sets.append(gold)
        predicted_sets.append(predicted)
        predicted_role = {(m.start, m.end, m.type): m for m in found}
        for span in record.spans:
            if span.type in ROLE_TYPES and span.role:
                match = predicted_role.get((span.start, span.end, span.type))
                guess = match.role if match and match.role else "missed"
                role_pairs.append((span.role, guess))
                for tag in record.tags:
                    per_tag_pairs[tag].append((span.role, guess))
                if match and match.role_probs:
                    role_probs.append([match.role_probs[r] for r in ROLES])
                    role_labels.append(ROLES.index(span.role))

    errors = [
        {"id": r.id, "missing": sorted(g - p), "extra": sorted(p - g)}
        for r, g, p in zip(records, gold_sets, predicted_sets, strict=True)
        if g != p
    ][:MAX_LISTED_ERRORS]
    labels = [*ROLES, "missed"]
    role_report = classification_report(role_pairs, labels) if role_pairs else {}
    report = {
        "records": len(records),
        "spans": span_scores(gold_sets, predicted_sets),
        "roles": role_report,
        "roles_by_tag": {
            tag: {"samples": len(p), "accuracy": sum(g == q for g, q in p) / len(p)}
            for tag, p in sorted(per_tag_pairs.items())
        },
        "spans_by_tag": _spans_by_tag(records, gold_sets, predicted_sets),
        "span_errors": errors,
        "seconds": seconds,
    }
    if role_probs:
        report["role_ece"] = expected_calibration_error(role_probs, role_labels)
    return report


def _spans_by_tag(records, gold_sets, predicted_sets) -> dict:
    grouped: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for record, g, p in zip(records, gold_sets, predicted_sets, strict=True):
        for tag in record.tags:
            grouped[tag][0].append(g)
            grouped[tag][1].append(p)
    return {tag: span_scores(g, p)["micro"] for tag, (g, p) in sorted(grouped.items())}


def evaluate_verification(
    engine: Engine, records: Sequence[VerificationRecord]
) -> dict:
    if not records:
        return {}
    pairs = [(query_of(r.requirement, r.id), passage_of(r)) for r in records]
    started = time.perf_counter()
    verdicts = engine.verify(pairs, _budget())
    seconds = time.perf_counter() - started
    outcomes = [(r.label, v.label) for r, v in zip(records, verdicts, strict=True)]
    report = classification_report(outcomes, list(VERDICT_LABELS))
    predicted_support = [(g, p) for g, p in outcomes if p == "supports"]
    report["false_support_rate"] = rate(
        sum(g != "supports" for g, _ in predicted_support), len(predicted_support)
    )
    gold_contradicts = [(g, p) for g, p in outcomes if g == "contradicts"]
    report["contradiction_recall"] = rate(
        sum(p == "contradicts" for _, p in gold_contradicts), len(gold_contradicts)
    )
    report["contradiction_read_as_support"] = rate(
        sum(p == "supports" for _, p in gold_contradicts), len(gold_contradicts)
    )
    by_tag: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record, outcome in zip(records, outcomes, strict=True):
        for tag in record.tags:
            by_tag[tag].append(outcome)
    report["by_tag"] = {
        tag: {"samples": len(p), "accuracy": sum(g == q for g, q in p) / len(p)}
        for tag, p in sorted(by_tag.items())
    }
    report["by_requirement_type"] = _accuracy_by(
        records, outcomes, lambda r: r.requirement.type
    )
    report["label_counts"] = label_counts([r.label for r in records])
    report["errors"] = [
        {"id": r.id, "gold": g, "predicted": p, "tags": r.tags}
        for r, (g, p) in zip(records, outcomes, strict=True)
        if g != p
    ][:MAX_LISTED_ERRORS]
    probs = [
        (v.probs, r.label) for r, v in zip(records, verdicts, strict=True) if v.probs
    ]
    if probs:
        report["ece"] = expected_calibration_error(
            [[p[label] for label in VERDICT_LABELS] for p, _ in probs],
            [VERDICT_LABELS.index(g) for _, g in probs],
        )
    report["seconds"] = seconds
    return report


def _accuracy_by(records, outcomes, key) -> dict:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record, outcome in zip(records, outcomes, strict=True):
        grouped[key(record)].append(outcome)
    return {
        k: {"samples": len(v), "accuracy": sum(g == p for g, p in v) / len(v)}
        for k, v in sorted(grouped.items())
    }


def evaluate_retrieval(engine: Engine, records: Sequence[RetrievalRecord]) -> dict:
    if not records:
        return {}
    ranked: list[list[bool]] = []
    by_tag: dict[str, list[list[bool]]] = defaultdict(list)
    started = time.perf_counter()
    for record in records:
        passages = [
            Passage(
                id=p.id, text=p.text, context="experience", section_kind="experience"
            )
            for p in record.passages
        ]
        relevant = {p.id for p in record.passages if p.relevant}
        query = query_of(Requirement(type="skill", value=record.query), record.id)
        found = engine.retrieve([query], passages, len(passages), _budget())[record.id]
        order = [c.passage_id for c in found]
        order += [
            p.id for p in passages if p.id not in order
        ]  # unretrieved passages rank last
        hits = [pid in relevant for pid in order]
        ranked.append(hits)
        for tag in record.tags:
            by_tag[tag].append(hits)
    return {
        **retrieval_scores(ranked),
        "by_tag": {t: retrieval_scores(r) for t, r in sorted(by_tag.items())},
        "seconds": time.perf_counter() - started,
    }


def evaluate(engine: Engine, records: Sequence[Record]) -> dict:
    return {
        "extraction": evaluate_extraction(
            engine, [r for r in records if isinstance(r, ExtractionRecord)]
        ),
        "retrieval": evaluate_retrieval(
            engine, [r for r in records if isinstance(r, RetrievalRecord)]
        ),
        "verification": evaluate_verification(
            engine, [r for r in records if isinstance(r, VerificationRecord)]
        ),
    }


def build_report(engine: Engine, files: Sequence[Path]) -> dict:
    records = [r for path in files for r in read_jsonl(path)]
    sources = label_counts([r.source for r in records])
    return {
        "engine": engine.info.model_dump(mode="json"),
        "data": {
            "files": [str(p) for p in files],
            "digest": dataset_digest(files),
            "records": len(records),
            "sources": sources,
        },
        "caveats": (
            [
                "Part of this data is synthetic; scores on synthetic data overstate performance on real résumés."
            ]
            if sources.get("synthetic")
            else []
        ),
        **evaluate(engine, records),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--engine", choices=["rules"], help="the rule-based baseline")
    group.add_argument(
        "--candidate",
        type=Path,
        help="a training run directory with extractor/, verifier/ and retriever/",
    )
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)

    if args.engine == "rules":
        from app.ml.rules import RulesEngine

        engine: Engine = RulesEngine()
    else:
        from ml.candidate import load_candidate_engine

        engine = load_candidate_engine(args.candidate, args.device)
    report = build_report(engine, args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
