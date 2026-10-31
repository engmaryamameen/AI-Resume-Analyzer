import json
from pathlib import Path

import pytest

from app.ml.manifest import ArtifactError, Manifest, current_fingerprint
from app.ml.provision import LOCK_FILE, _download
from app.ml.semantic import semantic_fingerprint, semantic_manifest


def test_semantic_lock_has_pinned_safe_pretrained_artifacts():
    manifest = Manifest.model_validate_json(LOCK_FILE.read_text())
    assert {entry.id for entry in manifest.models} == {"retriever", "verifier"}
    for entry in manifest.models:
        assert entry.origin == "pretrained"
        assert len(entry.base_revision) == 40
        assert entry.license == "Apache-2.0"
        assert any(item.path == "model.safetensors" for item in entry.files)
        assert all(len(item.sha256) == 64 and item.size > 0 for item in entry.files)
    assert len(semantic_fingerprint(manifest)) == 64


def test_semantic_manifest_rejects_substituted_provenance(tmp_path: Path):
    data = json.loads(LOCK_FILE.read_text())
    data["models"][0]["base_revision"] = "0" * 40
    (tmp_path / "semantic-manifest.json").write_text(json.dumps(data))
    with pytest.raises(ArtifactError, match="pinned model lock"):
        semantic_manifest(tmp_path)
    assert current_fingerprint(tmp_path) == "rules"


def test_disabled_models_do_not_mark_rule_reports_stale(tmp_path: Path):
    assert current_fingerprint(tmp_path, enabled=False) == "rules"


def test_provision_refuses_non_https_or_untrusted_sources(tmp_path: Path):
    artifact = Manifest.model_validate_json(LOCK_FILE.read_text()).models[0].files[0]
    for url in ("file:///etc/passwd", "https://example.com/model.safetensors"):
        with pytest.raises(ArtifactError, match="approved HTTPS"):
            _download(url, tmp_path / "artifact", artifact)


def test_provision_refuses_partial_symlinks(tmp_path: Path):
    artifact = Manifest.model_validate_json(LOCK_FILE.read_text()).models[0].files[0]
    protected = tmp_path / "protected"
    protected.write_text("unchanged")
    (tmp_path / "artifact.partial").symlink_to(protected)
    with pytest.raises(ArtifactError, match="symlink"):
        _download("https://huggingface.co/model", tmp_path / "artifact", artifact)
    assert protected.read_text() == "unchanged"


def test_semantic_hypothesis_keeps_explicit_skill_use_without_strengthening_claims():
    from app.ml.contracts import Query
    from app.ml.semantic import nli_hypothesis

    query = Query(
        id="python",
        retrieval_query="Python",
        hypothesis="The candidate has hands-on experience with Python.",
    )
    assert nli_hypothesis(query) == "This person has used Python."
    other = query.model_copy(update={"hypothesis": "The candidate holds a degree."})
    assert nli_hypothesis(other) == other.hypothesis
