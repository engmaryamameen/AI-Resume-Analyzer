from ml.holdout import validate_manifest


def test_empty_or_synthetic_benchmarks_cannot_pass_release_gate(tmp_path):
    result = validate_manifest({}, tmp_path, [])
    assert not result["passed"]
    assert "No independently labeled data supplied" in result["errors"]
    assert any("200 records" in error for error in result["errors"])
