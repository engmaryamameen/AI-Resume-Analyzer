"""Operator-invoked download of pinned pretrained artifacts; never called during inference."""

import argparse
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app.ml.artifacts import sha256_file, verify_manifest_files
from app.ml.manifest import ArtifactError, Manifest, ManifestFile

LOCK_FILE = Path(__file__).with_name("semantic-models.json")
SEMANTIC_MANIFEST = "semantic-manifest.json"
LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0.txt"


def _download(url: str, destination: Path, expected: ManifestFile) -> None:
    if destination.is_file() and destination.stat().st_size == expected.size:
        if sha256_file(destination) == expected.sha256:
            return
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in {
        "huggingface.co",
        "www.apache.org",
    }:
        raise ArtifactError("Model downloads require an approved HTTPS source")
    partial = destination.with_name(destination.name + ".partial")
    if partial.is_symlink():
        raise ArtifactError("Partial artifact must not be a symlink")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as stream:  # noqa: S310 - HTTPS source validated above; bytes checksum-verified
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > expected.size:
                        raise ArtifactError("Downloaded artifact exceeds its pinned size")
                    stream.write(chunk)
            if partial.stat().st_size != expected.size or sha256_file(partial) != expected.sha256:
                raise ArtifactError("Downloaded artifact does not match the pinned checksum")
            partial.replace(destination)
            return
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def provision(model_dir: Path) -> Manifest:
    model_dir.mkdir(parents=True, exist_ok=True)
    owner = model_dir.stat()
    manifest = Manifest.model_validate_json(LOCK_FILE.read_text())
    for entry in manifest.models:
        directory = model_dir / entry.directory
        if directory.is_symlink():
            raise ArtifactError("Model directory must not be a symlink")
        directory.mkdir(exist_ok=True)
        for artifact in entry.files:
            destination = directory / artifact.path
            if destination.is_symlink():
                raise ArtifactError("Model artifacts must not be symlinks")
            url = (
                LICENSE_URL
                if artifact.path == "LICENSE.txt"
                else (
                    f"https://huggingface.co/{entry.base_model}/resolve/"
                    f"{entry.base_revision}/{artifact.path}?download=true"
                )
            )
            _download(url, destination, artifact)
            if os.geteuid() == 0:
                os.chown(destination, owner.st_uid, owner.st_gid)
        if os.geteuid() == 0:
            os.chown(directory, owner.st_uid, owner.st_gid)
        entry.approved = True
        entry.approved_by = "operator-provisioned pinned model lock"
        entry.approved_on = datetime.now(UTC).isoformat()
        print(f"Verified {entry.base_model} at {entry.base_revision}", flush=True)
    problems = verify_manifest_files(model_dir, manifest)
    if problems:
        raise ArtifactError("; ".join(problems))
    target = model_dir / SEMANTIC_MANIFEST
    temporary = target.with_suffix(".tmp")
    temporary.write_text(manifest.model_dump_json(indent=2) + "\n")
    temporary.replace(target)
    if os.geteuid() == 0:
        os.chown(target, owner.st_uid, owner.st_gid)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models-dir", type=Path, default=Path(__file__).resolve().parents[3] / "models"
    )
    args = parser.parse_args()
    provision(args.models_dir)


if __name__ == "__main__":
    main()
