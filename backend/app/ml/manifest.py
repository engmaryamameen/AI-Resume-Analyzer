"""The model manifest: which model files may be loaded, and what is known about them.

`models/manifest.json` is committed; the weights are not. An entry is only usable when a person has
reviewed the model (licence, provenance, checksums) and set `approved`. Until then the worker runs the
rules engine. Nothing is ever downloaded by the application.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.ml.contracts import ModelRef

MANIFEST_NAME = "manifest.json"
REQUIRED_MODELS = ("extractor", "retriever", "verifier")


class ArtifactError(Exception):
    """A model artifact is missing, unapproved, altered or unsafe to load."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value and not path.is_absolute() and "\\" not in value
                and all(part not in ("", ".", "..") for part in value.split("/"))
                and not (len(value) >= 2 and value[1] == ":"))


class ManifestFile(BaseModel):
    path: str  # relative to the model directory
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_path(self):
        if not _safe_relative(self.path):
            raise ValueError("artifact path must be a safe relative path")
        return self


class TrainingProvenance(BaseModel):
    run_id: str
    dataset_manifest_sha256: str
    code_version: str
    report: str  # path of the evaluation report this model was approved on


class HeadCalibration(BaseModel):
    temperature: float = Field(gt=0)
    validation_samples: int = Field(ge=0)
    ece: float = Field(ge=0)  # measured on a split other than the one the temperature was fitted on


class DisplayPolicy(BaseModel):
    """Probabilities are shown only for a head whose calibration meets both limits (a policy choice)."""

    max_ece: float = 0.05
    min_validation_samples: int = 500


class ModelEntry(BaseModel):
    id: Literal["extractor", "retriever", "verifier"]
    directory: str
    origin: Literal["pretrained", "fine_tuned"]
    base_model: str
    base_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    license: str
    license_notes: str = ""
    training: TrainingProvenance | None = None
    files: list[ManifestFile] = Field(default_factory=list)
    calibration: dict[str, HeadCalibration] = Field(default_factory=dict)
    approved: bool = False
    approved_by: str | None = None
    approved_on: str | None = None

    @model_validator(mode="after")
    def validate_artifacts(self):
        if not _safe_relative(self.directory):
            raise ValueError("model directory must be a safe relative path")
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate artifact path")
        return self

    def ref(self) -> ModelRef:
        return ModelRef(id=self.id, origin=self.origin, base_model=self.base_model,
                        revision=self.base_revision, license=self.license)


class Manifest(BaseModel):
    manifest_version: int = 1
    display_policy: DisplayPolicy = Field(default_factory=DisplayPolicy)
    models: list[ModelEntry]

    @model_validator(mode="after")
    def validate_entries(self):
        ids = [entry.id for entry in self.models]
        directories = [entry.directory for entry in self.models]
        if len(ids) != len(set(ids)) or len(directories) != len(set(directories)):
            raise ValueError("duplicate model id or directory")
        return self

    def entry(self, model_id: str) -> ModelEntry | None:
        return next((m for m in self.models if m.id == model_id), None)

    def calibration_usable(self, entry: ModelEntry, head: str) -> bool:
        cal = entry.calibration.get(head)
        return bool(cal and cal.ece <= self.display_policy.max_ece
                    and cal.validation_samples >= self.display_policy.min_validation_samples)


def load_manifest(model_dir: Path) -> Manifest:
    path = model_dir / MANIFEST_NAME
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactError(f"No model manifest at {path}.") from exc
    except (ValidationError, ValueError) as exc:
        raise ArtifactError(f"The model manifest is invalid: {exc}") from exc


def fingerprint(manifest: Manifest) -> str:
    """"rules" unless every required model is approved; otherwise a hash of what was approved."""
    entries = [manifest.entry(i) for i in REQUIRED_MODELS]
    if any(e is None or not e.approved for e in entries):
        return "rules"
    material = [{"id": e.id, "files": sorted((f.path, f.sha256) for f in e.files),
                 "calibration": {k: v.model_dump() for k, v in sorted(e.calibration.items())}}
                for e in entries if e is not None]
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def current_fingerprint(model_dir: Path) -> str:
    try:
        return fingerprint(load_manifest(model_dir))
    except ArtifactError:
        return "rules"
