"""Optional model-runtime contract, exercised without loading model weights."""

import pytest


def test_local_retrieval_accepts_empty_queries():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from app.ml.contracts import Passage
    from app.ml.engine import Budget
    from app.ml.local import LocalEngine

    engine = object.__new__(LocalEngine)
    passage = Passage(id="p", text="Built Python APIs", context="experience", section_kind="experience")
    assert engine.retrieve([], [passage], 5, Budget(10)) == {}
