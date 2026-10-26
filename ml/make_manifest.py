"""Record file checksums, calibration and training provenance in models/manifest.json.

    python -m ml.make_manifest --models-dir models --run ml/runs/<name> --report ml/runs/<name>/test-report.json

For each model directory present it writes the file list with sizes and SHA-256 hashes. With `--run` it
also copies in the calibration and the training record of that run. It never sets `approved`: a person
reviews the licence, the data and the evaluation report, then edits the manifest.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.ml.artifacts import sha256_file
from app.ml.manifest import MANIFEST_NAME, HeadCalibration, Manifest, ManifestFile, TrainingProvenance

_HEADS = {"extractor": "role", "verifier": "verdict"}
_RUN_RECORD = {"extractor": "extractor-run.json", "verifier": "verifier-run.json"}


def describe_files(directory: Path) -> list[dict]:
    return [{"path": p.relative_to(directory).as_posix(), "sha256": sha256_file(p), "size": p.stat().st_size}
            for p in sorted(directory.rglob("*")) if p.is_file()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--run", type=Path, help="a training run whose calibration and provenance to record")
    parser.add_argument("--report", help="path of the evaluation report this model was judged on")
    args = parser.parse_args(argv)

    path = args.models_dir / MANIFEST_NAME
    manifest = Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    for entry in manifest.models:
        directory = args.models_dir / entry.directory
        if not directory.is_dir():
            print(f"{entry.id}: no directory at {directory}, left as is")
            continue
        new_files = describe_files(directory)
        if [f.model_dump() for f in entry.files] != new_files:
            entry.approved, entry.approved_by, entry.approved_on = False, None, None  # changed files need a new review
        entry.files = [ManifestFile(**f) for f in new_files]
        if args.run and entry.id in _HEADS:
            _record_run(entry, args.run, args.report)
        print(f"{entry.id}: {len(entry.files)} files recorded; approved={entry.approved}")
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return 0


def _record_run(entry, run: Path, report: str | None) -> None:
    record = json.loads((run / _RUN_RECORD[entry.id]).read_text(encoding="utf-8"))
    calibration = json.loads((run / "calibration.json").read_text(encoding="utf-8")).get(_HEADS[entry.id])
    if calibration:
        entry.calibration = {_HEADS[entry.id]: HeadCalibration(
            temperature=calibration["temperature"], validation_samples=calibration["validation_samples"],
            ece=calibration["ece"])}
    entry.training = TrainingProvenance(
        run_id=run.name, dataset_manifest_sha256=record["data"]["digest"],
        code_version=record["environment"]["code_version"], report=report or "")


if __name__ == "__main__":
    sys.exit(main())
