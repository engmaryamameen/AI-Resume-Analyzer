"""Fail-closed provenance gate for independent holdout data. No corpus is supplied or invented.

python -m ml.holdout --manifest private/holdout.json --training private/train/*.jsonl
"""

import argparse
import hashlib
import json
from pathlib import Path

from ml.schema import read_jsonl

REQUIRED_TAGS = {
    "negation",
    "contradiction",
    "ocr",
    "alternative_requirements",
    "dates",
    "degrees",
    "seniority",
    "multilingual",
    "out_of_domain",
}


def validate_manifest(manifest: dict, base: Path, training: list[Path]) -> dict:
    errors = []
    reviewers = manifest.get("independent_reviewers", [])
    if len(set(reviewers)) < 2 or not manifest.get("adjudication_complete"):
        errors.append(
            "Two independent annotators and completed adjudication are required"
        )
    if not manifest.get("rights_reference") or not manifest.get(
        "privacy_review_reference"
    ):
        errors.append("Rights and privacy review references are required")
    files = manifest.get("files", [])
    if not files:
        errors.append("No independently labeled data supplied")
    groups, identifiers, tags = set(), set(), set()
    total = 0
    digest = hashlib.sha256()
    for item in files:
        path = (base / item["path"]).resolve()
        if not path.is_relative_to(base.resolve()):
            errors.append("Holdout files must be inside the manifest directory")
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.get("sha256"):
            errors.append(f"Checksum mismatch: {path.name}")
        digest.update(raw)
        for record in read_jsonl(path):
            total += 1
            if record.source != "licensed":
                errors.append(
                    f"Independent holdout must use licensed/consented records: {record.id}"
                )
            if record.id in identifiers:
                errors.append(f"Duplicate record: {record.id}")
            identifiers.add(record.id)
            groups.add(record.group)
            tags.update(record.tags)
    training_groups = {record.group for path in training for record in read_jsonl(path)}
    if groups & training_groups:
        errors.append("Source/document groups overlap training or calibration data")
    if total < 200 or len(groups) < 50:
        errors.append(
            "Initial release requires at least 200 records from 50 independent source groups"
        )
    if REQUIRED_TAGS - tags:
        errors.append("Missing coverage: " + ", ".join(sorted(REQUIRED_TAGS - tags)))
    return {
        "passed": not errors,
        "errors": errors,
        "records": total,
        "source_groups": len(groups),
        "tags": sorted(tags),
        "content_digest": digest.hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--training", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    report = validate_manifest(
        json.loads(args.manifest.read_text()), args.manifest.parent, args.training
    )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
