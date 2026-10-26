"""Leakage-free dataset splits.

Records are assigned to a split by their `group` (template family, person or job posting), never one by
one, so near-identical records can't land on both sides of a split. Assignment is a pure function of the
group name and the seed: adding data later doesn't move existing groups.

    python -m ml.split --out ml/data/generated/splits ml/data/generated/synthetic.*.jsonl
"""

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ml.schema import SPLITS, Record, read_jsonl, write_jsonl

DEFAULT_FRACTIONS = {"train": 0.70, "validation": 0.10, "calibration": 0.10, "test": 0.10}


def assign(group: str, seed: int, fractions: dict[str, float] = DEFAULT_FRACTIONS) -> str:
    point = int.from_bytes(hashlib.sha256(f"{seed}:{group}".encode()).digest()[:8], "big") / 2**64
    edge = 0.0
    for split in SPLITS:
        edge += fractions[split]
        if point < edge:
            return split
    return SPLITS[-1]


def split_records(records: Sequence[Record], seed: int) -> dict[str, list[Record]]:
    out: dict[str, list[Record]] = {s: [] for s in SPLITS}
    for record in records:
        out[assign(record.group, seed)].append(record)
    return out


def write_splits(records: Sequence[Record], out_dir: Path, seed: int, prefix: str) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for split, items in split_records(records, seed).items():
        by_kind: dict[str, list[Record]] = {}
        for record in items:
            by_kind.setdefault(record.kind, []).append(record)
        summary[split] = {}
        for kind, rows in by_kind.items():
            write_jsonl(out_dir / f"{split}.{prefix}-{kind}.jsonl", rows)
            summary[split][kind] = len(rows)
    return summary


def load_split(directory: Path, split: str, kind: str) -> list[Record]:
    """All records of one kind in one split of a directory written by `write_splits`."""
    return [r for path in sorted(directory.glob(f"{split}.*-{kind}.jsonl")) for r in read_jsonl(path)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--prefix", default="data")
    args = parser.parse_args(argv)
    records = [r for path in args.files for r in read_jsonl(path)]
    summary = write_splits(records, args.out, args.seed, args.prefix)
    (args.out / "splits.json").write_text(
        json.dumps({"seed": args.seed, "fractions": DEFAULT_FRACTIONS, "counts": summary}, indent=2, sort_keys=True), encoding="utf-8")
    for split, counts in summary.items():
        print(split, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
