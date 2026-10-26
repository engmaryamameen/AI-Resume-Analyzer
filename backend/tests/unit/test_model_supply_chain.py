"""Model manifest, approval and file verification.

Invariants: nothing loads unless a person approved it; every file matches its recorded checksum; nothing
unlisted can sit beside approved files; formats that execute code on load are refused; the fingerprint
changes whenever an approved file or calibration changes.
"""

import json

import pytest

from app.ml.artifacts import entry_problems, sha256_file, verified_entry_dir
from app.ml.manifest import (
    ArtifactError,
    HeadCalibration,
    Manifest,
    ManifestFile,
    ModelEntry,
    fingerprint,
    load_manifest,
)

REVISION = "a" * 40


def provision(tmp_path, model_id="extractor", files=None, **overrides):
    """Writes a model directory and returns the manifest entry that describes it."""
    directory = tmp_path / model_id
    directory.mkdir(parents=True, exist_ok=True)
    files = files or {"model.safetensors": b"weights", "config.json": b"{}"}
    for name, data in files.items():
        (directory / name).write_bytes(data)
    listed = [ManifestFile(path=n, sha256=sha256_file(directory / n), size=len(d)) for n, d in files.items()]
    fields = dict(id=model_id, directory=model_id, origin="fine_tuned", base_model="base", base_revision=REVISION,
                  license="Apache-2.0", files=listed, approved=True)
    return ModelEntry(**{**fields, **overrides})


def manifest_of(tmp_path, approved=True):
    entries = [provision(tmp_path, i, approved=approved) for i in ("extractor", "retriever", "verifier")]
    return Manifest(models=entries)


class TestManifestFile:
    def test_missing_manifest_is_an_artifact_error(self, tmp_path):
        with pytest.raises(ArtifactError):
            load_manifest(tmp_path)

    def test_invalid_manifest_is_an_artifact_error(self, tmp_path):
        (tmp_path / "manifest.json").write_text("{not json")
        with pytest.raises(ArtifactError):
            load_manifest(tmp_path)

    def test_revision_must_be_a_full_commit_hash(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps(
            {"models": [{"id": "extractor", "directory": "e", "origin": "pretrained", "base_model": "b",
                         "base_revision": "main", "license": "MIT"}]}))
        with pytest.raises(ArtifactError):
            load_manifest(tmp_path)

    def test_the_committed_manifest_is_valid_and_nothing_in_it_is_approved(self):
        from app.core.config import REPO_ROOT

        manifest = load_manifest(REPO_ROOT / "models")
        assert {m.id for m in manifest.models} == {"extractor", "retriever", "verifier"}
        assert not any(m.approved for m in manifest.models)
        assert fingerprint(manifest) == "rules"


class TestFingerprint:
    def test_rules_until_every_model_is_approved(self, tmp_path):
        manifest = manifest_of(tmp_path)
        manifest.models[1].approved = False
        assert fingerprint(manifest) == "rules"

    def test_changes_when_a_file_changes(self, tmp_path):
        manifest = manifest_of(tmp_path)
        before = fingerprint(manifest)
        manifest.models[0].files[0] = manifest.models[0].files[0].model_copy(update={"sha256": "b" * 64})
        assert before != "rules" and fingerprint(manifest) != before

    def test_changes_when_calibration_changes(self, tmp_path):
        manifest = manifest_of(tmp_path)
        before = fingerprint(manifest)
        manifest.models[2].calibration = {"verdict": HeadCalibration(temperature=1.4, validation_samples=800, ece=0.03)}
        assert fingerprint(manifest) != before

    def test_probabilities_need_enough_samples_and_a_small_error(self, tmp_path):
        manifest = manifest_of(tmp_path)
        entry = manifest.models[2]
        entry.calibration = {"verdict": HeadCalibration(temperature=1.2, validation_samples=800, ece=0.03)}
        assert manifest.calibration_usable(entry, "verdict")
        entry.calibration = {"verdict": HeadCalibration(temperature=1.2, validation_samples=100, ece=0.03)}
        assert not manifest.calibration_usable(entry, "verdict")
        entry.calibration = {"verdict": HeadCalibration(temperature=1.2, validation_samples=800, ece=0.2)}
        assert not manifest.calibration_usable(entry, "verdict")
        assert not manifest.calibration_usable(entry, "role")


@pytest.mark.security
class TestFileVerification:
    def test_intact_approved_model_has_no_problems(self, tmp_path):
        entry = provision(tmp_path)
        assert entry_problems(tmp_path, entry) == []
        assert verified_entry_dir(tmp_path, entry) == tmp_path / "extractor"

    def test_unapproved_model_is_refused(self, tmp_path):
        with pytest.raises(ArtifactError, match="not been approved"):
            verified_entry_dir(tmp_path, provision(tmp_path, approved=False))

    def test_unprovisioned_entry_is_reported(self, tmp_path):
        entry = provision(tmp_path).model_copy(update={"files": []})
        assert "not provisioned" in entry_problems(tmp_path, entry)[0]

    def test_a_changed_file_is_detected(self, tmp_path):
        entry = provision(tmp_path)
        (tmp_path / "extractor" / "model.safetensors").write_bytes(b"tampered")
        assert any("checksum" in p for p in entry_problems(tmp_path, entry))

    def test_a_missing_file_is_detected(self, tmp_path):
        entry = provision(tmp_path)
        (tmp_path / "extractor" / "config.json").unlink()
        assert any("missing" in p for p in entry_problems(tmp_path, entry))

    def test_an_unlisted_file_is_detected(self, tmp_path):
        entry = provision(tmp_path)
        (tmp_path / "extractor" / "planted.py").write_text("print('hi')")
        assert any("unlisted file planted.py" in p for p in entry_problems(tmp_path, entry))

    @pytest.mark.parametrize("name", ["weights.bin", "weights.pt", "weights.pkl", "model.ckpt", "arrays.npy"])
    def test_formats_that_unpickle_are_refused(self, tmp_path, name):
        entry = provision(tmp_path, files={"model.safetensors": b"w", name: b"x"})
        assert any("execute code" in p for p in entry_problems(tmp_path, entry))

    def test_custom_code_in_a_config_is_refused(self, tmp_path):
        entry = provision(tmp_path, files={"model.safetensors": b"w", "config.json": b'{"auto_map": {"AutoModel": "x.Y"}}'})
        assert any("auto_map" in p for p in entry_problems(tmp_path, entry))

    def test_safetensors_weights_are_required(self, tmp_path):
        entry = provision(tmp_path, files={"config.json": b"{}"})
        assert any("safetensors" in p for p in entry_problems(tmp_path, entry))
