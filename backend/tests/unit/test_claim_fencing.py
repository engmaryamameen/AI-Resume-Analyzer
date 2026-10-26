"""Regression contracts for attempt-specific leases and artifact-path validation."""

import pytest
from pydantic import ValidationError
from app.ml.manifest import Manifest, ManifestFile, ModelEntry


def test_manifest_rejects_unsafe_paths():
    for unsafe in ('../outside', '/tmp/weights', 'config/../../other', r'C:\\secret'):
        with pytest.raises(ValidationError):
            ManifestFile(path=unsafe, sha256='0' * 64, size=1)


def test_manifest_rejects_duplicate_models():
    entry = ModelEntry(id='retriever', directory='retriever', origin='pretrained',
                       base_model='example', base_revision='0' * 40, license='MIT')
    with pytest.raises(ValidationError):
        Manifest(models=[entry, entry])

