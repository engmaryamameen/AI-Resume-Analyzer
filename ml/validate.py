"""Dataset validation: structure, span correctness, duplicates and leakage. Torch-free.

    python -m ml.validate ml/data/challenge/*.jsonl
    python -m ml.validate --splits ml/data/generated/splits

Exit status is non-zero if any error is found. Warnings are reported but do not fail the run.
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.lang.taxonomy import get_taxonomy
from app.ml.decoding import MAX_CHUNK_CHARS
from ml.schema import (
    SPLITS,
    ExtractionRecord,
    Record,
    RetrievalRecord,
    VerificationRecord,
    read_jsonl,
)

NEAR_DUPLICATE_JACCARD = 0.9
_WORD = re.compile(r"\w+")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.errors


def normalized(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def shingles(text: str, n: int = 3) -> frozenset[str]:
    words = _WORD.findall(text.lower())
    if len(words) < n:
        return frozenset({" ".join(words)})
    return frozenset(" ".join(words[i: i + n]) for i in range(len(words) - n + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def record_texts(record: Record) -> list[str]:
    if isinstance(record, RetrievalRecord):
        return [p.text for p in record.passages]
    return [record.text]


def check_record(record: Record, report: Report) -> None:
    where = f"{record.id}"
    for text in record_texts(record):
        if not text.strip():
            report.errors.append(f"{where}: empty text")
        if len(text) > MAX_CHUNK_CHARS:
            report.errors.append(f"{where}: text longer than {MAX_CHUNK_CHARS} characters")
    if isinstance(record, ExtractionRecord):
        _check_spans(record, report)
    elif isinstance(record, VerificationRecord):
        _check_requirement(record, report)
    elif isinstance(record, RetrievalRecord):
        if not any(p.relevant for p in record.passages):
            report.errors.append(f"{where}: no relevant passage")
        if len({p.id for p in record.passages}) != len(record.passages):
            report.errors.append(f"{where}: duplicate passage ids")


def _check_requirement(record: VerificationRecord, report: Report) -> None:
    value = record.requirement.value
    if not value.strip():
        report.errors.append(f"{record.id}: empty requirement")
        return
    if record.requirement.type in {"skill", "soft_skill"}:
        taxonomy = get_taxonomy()
        term_id = taxonomy.normalise_surface(value)
        if term_id is not None and taxonomy.get(term_id).name != value:
            # The application words the hypothesis with the vocabulary's canonical name; so must the data.
            report.errors.append(f"{record.id}: requirement {value!r} should be written as {taxonomy.get(term_id).name!r}")


def _check_spans(record: ExtractionRecord, report: Report) -> None:
    last_end = 0
    for span in sorted(record.spans, key=lambda s: (s.start, s.end)):
        if span.end > len(record.text):
            report.errors.append(f"{record.id}: span {span.start}-{span.end} is outside the text")
            continue
        if span.start < last_end:
            report.errors.append(f"{record.id}: overlapping spans near offset {span.start}")
        last_end = max(last_end, span.end)
        surface = record.text[span.start: span.end]
        if surface != surface.strip():
            report.errors.append(f"{record.id}: span {surface!r} has surrounding whitespace")
        before = record.text[span.start - 1] if span.start else " "
        after = record.text[span.end] if span.end < len(record.text) else " "
        if (before.isalnum() and surface[0].isalnum()) or (after.isalnum() and surface[-1].isalnum()):
            report.warnings.append(f"{record.id}: span {surface!r} starts or ends inside a word")


def check_records(records: Sequence[Record]) -> Report:
    report = Report()
    seen_ids: set[str] = set()
    for record in records:
        report.counts[f"{record.kind}:{record.source}"] += 1
        if record.id in seen_ids:
            report.errors.append(f"{record.id}: duplicate id")
        seen_ids.add(record.id)
        check_record(record, report)
        if isinstance(record, VerificationRecord):
            report.counts[f"label:{record.label}"] += 1
    _check_duplicates(records, report)
    return report


def _check_duplicates(records: Sequence[Record], report: Report) -> None:
    first_seen: dict[str, str] = {}
    for record in records:
        if isinstance(record, VerificationRecord):
            key = normalized(record.text) + "||" + normalized(record.requirement.value)
        elif isinstance(record, ExtractionRecord):
            key = normalized(record.text)
        else:
            continue
        if key in first_seen:
            report.warnings.append(f"{record.id}: same text as {first_seen[key]}")
        else:
            first_seen[key] = record.id


def check_splits(directory: Path) -> Report:
    """Leakage checks across the train / validation / calibration / test files in `directory`."""
    report = Report()
    by_split: dict[str, list[Record]] = {}
    for split in SPLITS:
        records: list[Record] = []
        for path in sorted(directory.glob(f"{split}.*.jsonl")):
            records.extend(read_jsonl(path))
        by_split[split] = records
        sub = check_records(records)
        report.errors += [f"[{split}] {e}" for e in sub.errors]
        report.warnings += [f"[{split}] {w}" for w in sub.warnings]
        report.counts.update({f"{split}:{k}": v for k, v in sub.counts.items()})

    groups: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, set[str]] = defaultdict(set)
    for split, records in by_split.items():
        for record in records:
            groups[record.group].add(split)
            for text in record_texts(record):
                texts[normalized(text)].add(split)
    for group, splits in sorted(groups.items()):
        if len(splits) > 1:
            report.errors.append(f"group {group!r} appears in several splits: {sorted(splits)}")
    for text, splits in texts.items():
        if len(splits) > 1:
            report.errors.append(f"identical text in several splits {sorted(splits)}: {text[:60]!r}")

    train = [(r.id, shingles(t)) for r in by_split["train"] for t in record_texts(r)]
    for split in SPLITS[1:]:
        for record in by_split[split]:
            for text in record_texts(record):
                grams = shingles(text)
                for other_id, other in train:
                    if jaccard(grams, other) >= NEAR_DUPLICATE_JACCARD:
                        report.errors.append(f"near-duplicate of training record {other_id}: {record.id} ({split})")
                        break
    return report


def print_report(report: Report) -> None:
    for line in report.warnings:
        print(f"warning: {line}")
    for line in report.errors:
        print(f"error: {line}")
    for key, value in sorted(report.counts.items()):
        print(f"{key}: {value}")
    print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--splits", type=Path, help="a directory produced by ml.split")
    args = parser.parse_args(argv)
    if args.splits:
        report = check_splits(args.splits)
    elif args.files:
        records = [r for path in args.files for r in read_jsonl(path)]
        report = check_records(records)
    else:
        parser.error("give dataset files or --splits")
    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
