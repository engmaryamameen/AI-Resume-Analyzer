"""Pretrained local retrieval/NLI with deterministic entity and date handling."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.ml.artifacts import verified_entry_dir
from app.ml.contracts import Candidate, EngineInfo, Mention, Passage, Query, Verdict, VerdictLabel
from app.ml.engine import Budget, EngineUnavailable
from app.ml.manifest import ArtifactError, Manifest
from app.ml.rules import RulesEngine

SEMANTIC_MANIFEST = "semantic-manifest.json"
SEMANTIC_IDS = {"retriever", "verifier"}


def nli_hypothesis(query: Query) -> str:
    prefix = "The candidate has hands-on experience with "
    if query.hypothesis.startswith(prefix):
        return "This person has used " + query.hypothesis[len(prefix) :]
    return query.hypothesis


def semantic_manifest(model_dir: Path, *, verify: bool = False) -> Manifest:
    path = model_dir / SEMANTIC_MANIFEST
    manifest = Manifest.model_validate_json(path.read_text())
    if {entry.id for entry in manifest.models} != SEMANTIC_IDS:
        raise ArtifactError("Semantic inference requires the retriever and verifier")
    locked = Manifest.model_validate_json(
        Path(__file__).with_name("semantic-models.json").read_text()
    )
    if len(manifest.models) != len(locked.models):
        raise ArtifactError("Unexpected semantic model entries")
    for entry in manifest.models:
        expected = locked.entry(entry.id)
        if expected is None or any(
            getattr(entry, key) != getattr(expected, key)
            for key in ("directory", "origin", "base_model", "base_revision", "license", "files")
        ):
            raise ArtifactError("Semantic artifacts differ from the pinned model lock")
        directory = model_dir / entry.directory
        if directory.is_symlink() or not directory.resolve().is_relative_to(model_dir.resolve()):
            raise ArtifactError("Unsafe semantic model directory")
        if entry.origin != "pretrained" or not entry.approved or not entry.files:
            raise ArtifactError("Semantic model artifacts are not provisioned")
        for artifact in entry.files:
            target = model_dir / entry.directory / artifact.path
            if (
                target.is_symlink()
                or not target.is_file()
                or target.stat().st_size != artifact.size
            ):
                raise ArtifactError("Semantic model artifact is missing or altered")
        if verify:
            verified_entry_dir(model_dir, entry)
    return manifest


def semantic_fingerprint(manifest: Manifest) -> str:
    material = sorted(
        (entry.id, entry.base_revision, f.path, f.sha256)
        for entry in manifest.models
        for f in entry.files
    )
    return hashlib.sha256(json.dumps(["semantic-v1", material]).encode()).hexdigest()


class SemanticEngine:
    def __init__(
        self,
        settings: Settings,
        manifest: Manifest,
        torch: Any,
        encoder: Any,
        tokenizer: Any,
        verifier: Any,
        verifier_tokenizer: Any,
    ):
        self._settings = settings
        self._torch = torch
        self._encoder, self._tokenizer = encoder, tokenizer
        self._verifier, self._verifier_tokenizer = verifier, verifier_tokenizer
        self._rules = RulesEngine()
        self.info = EngineInfo(
            mode="semantic",
            models=[entry.ref() for entry in manifest.models],
            calibrated=False,
            fingerprint=semantic_fingerprint(manifest),
            notes=[
                "Pretrained local models retrieve and compare passage meaning. Entity roles and dates use deterministic rules.",
                "Model outputs are not calibrated hiring probabilities.",
            ],
        )
        self._labels = {
            int(index): str(label).lower() for index, label in verifier.config.id2label.items()
        }
        if set(self._labels.values()) != {"contradiction", "entailment", "neutral"}:
            raise ArtifactError("The pretrained NLI label mapping is incompatible")

    @classmethod
    def load(cls, settings: Settings) -> "SemanticEngine":
        import os

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        import torch
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

        manifest = semantic_manifest(settings.model_dir, verify=True)
        torch.set_num_threads(settings.ml_threads)
        if settings.ml_device == "cuda" and not torch.cuda.is_available():
            raise ArtifactError("CUDA was requested but is unavailable")
        retriever = manifest.entry("retriever")
        verifier = manifest.entry("verifier")
        assert retriever is not None and verifier is not None
        retrieval_dir = settings.model_dir / retriever.directory
        verifier_dir = settings.model_dir / verifier.directory
        load_options = {"local_files_only": True, "trust_remote_code": False}
        encoder = (
            AutoModel.from_pretrained(retrieval_dir, use_safetensors=True, **load_options)
            .to(settings.ml_device)
            .eval()
        )
        nli = (
            AutoModelForSequenceClassification.from_pretrained(
                verifier_dir, use_safetensors=True, **load_options
            )
            .to(settings.ml_device)
            .eval()
        )
        return cls(
            settings,
            manifest,
            torch,
            encoder,
            AutoTokenizer.from_pretrained(retrieval_dir, **load_options),
            nli,
            AutoTokenizer.from_pretrained(verifier_dir, **load_options),
        )

    def extract(self, passages: Sequence[Passage], budget: Budget) -> list[Mention]:
        return self._rules.extract(passages, budget)

    def _encode(self, texts: Sequence[str], budget: Budget) -> Any:
        batches = []
        for offset in range(0, len(texts), self._settings.ml_batch_size):
            budget.check()
            tokens = self._tokenizer(
                list(texts[offset : offset + self._settings.ml_batch_size]),
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            ).to(self._settings.ml_device)
            with self._torch.inference_mode():
                hidden = self._encoder(**tokens).last_hidden_state
                mask = tokens["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
                batches.append(self._torch.nn.functional.normalize(pooled, p=2, dim=1))
        return self._torch.cat(batches)

    def retrieve(
        self, queries: Sequence[Query], passages: Sequence[Passage], k: int, budget: Budget
    ) -> dict[str, list[Candidate]]:
        if not passages or not queries:
            return {q.id: [] for q in queries}
        try:
            documents = self._encode([p.text for p in passages], budget)
            questions = self._encode([q.retrieval_query for q in queries], budget)
            similarities = questions @ documents.T
            result = {}
            for i, query in enumerate(queries):
                values, indices = similarities[i].topk(min(k, len(passages)))
                result[query.id] = [
                    Candidate(
                        passage_id=passages[int(index)].id, score=float(score), method="embedding"
                    )
                    for score, index in zip(values.tolist(), indices.tolist(), strict=True)
                ]
            return result
        except RuntimeError as exc:
            raise EngineUnavailable("Local semantic retrieval could not complete") from exc

    def verify(self, pairs: Sequence[tuple[Query, Passage]], budget: Budget) -> list[Verdict]:
        verdicts = []
        try:
            for offset in range(0, len(pairs), self._settings.ml_batch_size):
                budget.check()
                batch = pairs[offset : offset + self._settings.ml_batch_size]
                tokens = self._verifier_tokenizer(
                    [p.text for _, p in batch],
                    [nli_hypothesis(q) for q, _ in batch],
                    padding=True,
                    truncation=True,
                    max_length=384,
                    return_tensors="pt",
                ).to(self._settings.ml_device)
                with self._torch.inference_mode():
                    probabilities = self._torch.softmax(self._verifier(**tokens).logits, dim=-1)
                for row in probabilities.tolist():
                    scores = {self._labels[i]: float(value) for i, value in enumerate(row)}
                    label: VerdictLabel = "unrelated"
                    if scores["entailment"] >= 0.70:
                        label = "supports"
                    elif scores["contradiction"] >= 0.85:
                        label = "contradicts"
                    verdicts.append(Verdict(label=label, source="learned", probs=None))
            return verdicts
        except RuntimeError as exc:
            raise EngineUnavailable("Local semantic verification could not complete") from exc
