"""Load a freshly trained set of models as an engine, for evaluation before anything is approved.

A run directory holds `extractor/`, `verifier/`, a `retriever/` copy of the provisioned retrieval model and
the `calibration.json` written by ml.calibrate. The in-memory manifest marks the entries approved so the
engine will run them; nothing is written back, and the application's own manifest is untouched.
"""

import json
from pathlib import Path

from app.core.config import REPO_ROOT
from app.ml.local import LocalEngine
from app.ml.manifest import (
    REQUIRED_MODELS,
    ArtifactError,
    HeadCalibration,
    load_manifest,
)

_HEADS = {"extractor": "role", "verifier": "verdict"}


def load_candidate_engine(run_dir: Path, device: str = "cpu") -> LocalEngine:
    manifest = load_manifest(REPO_ROOT / "models")
    directories = {}
    for model_id in REQUIRED_MODELS:
        directory = run_dir / model_id
        if not directory.is_dir():
            raise ArtifactError(f"{directory} is missing.")
        directories[model_id] = directory

    calibration_path = run_dir / "calibration.json"
    calibration = (
        json.loads(calibration_path.read_text(encoding="utf-8"))
        if calibration_path.is_file()
        else {}
    )
    for entry in manifest.models:
        entry.approved = True  # in memory only: this manifest is never saved
        head = _HEADS.get(entry.id)
        if head and head in calibration:
            entry.calibration = {
                head: HeadCalibration(
                    temperature=calibration[head]["temperature"],
                    validation_samples=calibration[head]["validation_samples"],
                    ece=calibration[head]["ece"],
                )
            }
    return LocalEngine(manifest, directories, device=device, threads=4, batch_size=16)
