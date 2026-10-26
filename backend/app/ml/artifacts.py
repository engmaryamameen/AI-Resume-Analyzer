"""Verification of model files before they are loaded.

Rules, all enforced before any weight is read:
  * the entry must be approved by a person;
  * every file must be listed in the manifest with its SHA-256, and nothing unlisted may sit in the
    directory (so a planted file cannot be picked up);
  * weights must be `.safetensors`; formats that deserialise with pickle are refused outright, because
    unpickling an untrusted file executes code;
  * configs must not use `auto_map`, which would make the loader import code shipped with the model.
"""

import hashlib
import json
from pathlib import Path

from app.ml.manifest import ArtifactError, Manifest, ModelEntry

_FORBIDDEN_SUFFIXES = {".bin", ".pt", ".pth", ".pkl", ".pickle", ".ckpt", ".joblib", ".npy", ".npz", ".msgpack", ".h5"}
_CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def entry_problems(model_dir: Path, entry: ModelEntry) -> list[str]:
    problems = []
    root = model_dir.resolve()
    directory = model_dir / entry.directory
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        return [f"{entry.id}: model directory escapes approved root"]
    if not entry.files:
        return [f"{entry.id}: no files recorded (not provisioned)"]
    listed = {f.path for f in entry.files}
    for item in entry.files:
        suffix = Path(item.path).suffix.lower()
        if suffix in _FORBIDDEN_SUFFIXES:
            problems.append(f"{entry.id}: {item.path} uses a format that can execute code when loaded")
            continue
        path = directory / item.path
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            problems.append(f"{entry.id}: unsafe artifact path {item.path}")
        elif not path.is_file():
            problems.append(f"{entry.id}: {item.path} is missing")
        elif path.stat().st_size != item.size or sha256_file(path) != item.sha256:
            problems.append(f"{entry.id}: {item.path} does not match its recorded checksum")
    if directory.is_dir():
        for found in directory.rglob("*"):
            if found.is_symlink():
                problems.append(f"{entry.id}: symlink forbidden: {found.relative_to(directory)}")
        present = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        problems += [f"{entry.id}: unlisted file {extra}" for extra in sorted(present - listed)]
    config = directory / "config.json"
    if config.is_symlink():
        problems.append(f"{entry.id}: config symlink forbidden")
    elif config.is_file() and "auto_map" in json.loads(config.read_text(encoding="utf-8")):
        problems.append(f"{entry.id}: config.json declares auto_map (custom code), which is not allowed")
    if not any(Path(f.path).suffix == ".safetensors" for f in entry.files):
        problems.append(f"{entry.id}: no .safetensors weights listed")
    return problems


def verify_manifest_files(model_dir: Path, manifest: Manifest) -> list[str]:
    problems = []
    for entry in manifest.models:
        if not entry.approved:
            problems.append(f"{entry.id}: not approved")
        problems += entry_problems(model_dir, entry)
    return problems


def verified_entry_dir(model_dir: Path, entry: ModelEntry) -> Path:
    if not entry.approved:
        raise ArtifactError(f"Model '{entry.id}' has not been approved.")
    problems = entry_problems(model_dir, entry)
    if problems:
        raise ArtifactError("; ".join(problems[:3]))
    return model_dir / entry.directory
