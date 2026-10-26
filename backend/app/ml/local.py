"""The learned engine: three locally executed neural models behind the `Engine` interface.

  extractor  fine-tuned encoder: entity spans and the role of each skill/degree/certification mention
  retriever  pretrained embedding model: finds the résumé passages most similar to a requirement
  verifier   fine-tuned cross-encoder: does this passage support, only mention, contradict, say too
             little about, or have nothing to do with the requirement

Everything is loaded once, from checksum-verified, approved safetensors files, with the Hugging Face
libraries forced offline. Inference is bounded: batches, a wall-clock budget checked between batches,
and out-of-memory conditions surface as EngineUnavailable so the caller can fall back cleanly.
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from collections.abc import Iterator, Sequence  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

import torch  # noqa: E402
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.ml.artifacts import verified_entry_dir  # noqa: E402
from app.ml.calibration import softmax  # noqa: E402
from app.ml.contracts import (  # noqa: E402
    VERDICT_LABELS,
    Candidate,
    EngineInfo,
    Mention,
    Passage,
    Query,
    Verdict,
)
from app.ml.decoding import chunk_text  # noqa: E402
from app.ml.engine import Budget, EngineUnavailable  # noqa: E402
from app.ml.manifest import REQUIRED_MODELS, ArtifactError, Manifest, ModelEntry, fingerprint, load_manifest  # noqa: E402
from app.ml.models import extract_batch, load_extractor  # noqa: E402

VERIFIER_MAX_TOKENS = 320
RETRIEVER_MAX_TOKENS = 192
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # required by the BGE retrieval model


@contextmanager
def _guard_memory() -> Iterator[None]:
    try:
        yield
    except torch.cuda.OutOfMemoryError as exc:
        raise EngineUnavailable("out_of_memory") from exc
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise EngineUnavailable("out_of_memory") from exc
        raise


class LocalEngine:
    def __init__(self, manifest: Manifest, directories: dict[str, Path], *, device: str, threads: int, batch_size: int):
        self._device = torch.device(device)
        torch.set_num_threads(threads)
        self._batch = batch_size

        self._extractor, self._extractor_tokenizer = load_extractor(directories["extractor"], self._device)
        self._retriever = AutoModel.from_pretrained(
            directories["retriever"], local_files_only=True, use_safetensors=True).to(self._device).eval()
        self._retriever_tokenizer = AutoTokenizer.from_pretrained(directories["retriever"], local_files_only=True)
        self._verifier = AutoModelForSequenceClassification.from_pretrained(
            directories["verifier"], local_files_only=True, use_safetensors=True).to(self._device).eval()
        self._verifier_tokenizer = AutoTokenizer.from_pretrained(directories["verifier"], local_files_only=True)
        if [self._verifier.config.id2label[i] for i in range(len(VERDICT_LABELS))] != list(VERDICT_LABELS):
            raise ArtifactError("The verifier's label set differs from the one this application uses.")

        entries = {e.id: e for e in manifest.models}
        self._role_temperature = self._temperature(manifest, entries["extractor"], "role")
        self._verdict_temperature = self._temperature(manifest, entries["verifier"], "verdict")
        self.info = EngineInfo(
            mode="learned", models=[entries[i].ref() for i in REQUIRED_MODELS],
            calibrated=self._role_temperature is not None and self._verdict_temperature is not None,
            fingerprint=fingerprint(manifest))

    @staticmethod
    def _temperature(manifest: Manifest, entry: ModelEntry, head: str) -> float | None:
        return entry.calibration[head].temperature if manifest.calibration_usable(entry, head) else None

    @classmethod
    def load(cls, settings: Settings) -> "LocalEngine":
        manifest = load_manifest(settings.model_dir)
        entries = {e.id: e for e in manifest.models}
        missing = [i for i in REQUIRED_MODELS if i not in entries]
        if missing:
            raise ArtifactError(f"The manifest has no entry for: {', '.join(missing)}.")
        if settings.ml_device == "cuda" and not torch.cuda.is_available():
            raise ArtifactError("ML_DEVICE=cuda but no CUDA device is available.")
        directories = {i: verified_entry_dir(settings.model_dir, entries[i]) for i in REQUIRED_MODELS}
        return cls(manifest, directories, device=settings.ml_device, threads=settings.ml_threads,
                   batch_size=settings.ml_batch_size)

    # ----- extraction -----------------------------------------------------------------------------
    def extract(self, passages: Sequence[Passage], budget: Budget) -> list[Mention]:
        pieces = [(p, offset, chunk) for p in passages for offset, chunk in chunk_text(p.text)]
        pieces.sort(key=lambda item: len(item[2]))
        mentions: list[Mention] = []
        with _guard_memory(), torch.inference_mode():
            for i in range(0, len(pieces), self._batch):
                budget.check()
                mentions.extend(self._extract_batch(pieces[i: i + self._batch]))
        return sorted(mentions, key=lambda m: (m.passage_id, m.start))

    def _extract_batch(self, batch: Sequence[tuple[Passage, int, str]]) -> list[Mention]:
        return extract_batch(self._extractor, self._extractor_tokenizer, batch, self._device, self._role_temperature)

    # ----- retrieval ------------------------------------------------------------------------------
    def retrieve(
        self, queries: Sequence[Query], passages: Sequence[Passage], k: int, budget: Budget
    ) -> dict[str, list[Candidate]]:
        if not passages:
            return {q.id: [] for q in queries}
        with _guard_memory(), torch.inference_mode():
            passage_vectors = self._embed([p.text for p in passages], budget)
            query_vectors = self._embed([QUERY_PREFIX + q.retrieval_query for q in queries], budget)
            scores = query_vectors @ passage_vectors.T
            top = scores.topk(min(k, len(passages)), dim=1)
        return {
            query.id: [Candidate(passage_id=passages[j].id, score=float(s), method="embedding")
                       for s, j in zip(top.values[i].tolist(), top.indices[i].tolist(), strict=True)]
            for i, query in enumerate(queries)
        }

    def _embed(self, texts: Sequence[str], budget: Budget) -> torch.Tensor:
        vectors = []
        for i in range(0, len(texts), self._batch):
            budget.check()
            encoded = self._retriever_tokenizer(
                list(texts[i: i + self._batch]), truncation=True, max_length=RETRIEVER_MAX_TOKENS,
                padding=True, return_tensors="pt").to(self._device)
            cls = self._retriever(**encoded).last_hidden_state[:, 0]
            vectors.append(torch.nn.functional.normalize(cls, dim=-1))
        return torch.cat(vectors)

    # ----- verification ---------------------------------------------------------------------------
    def verify(self, pairs: Sequence[tuple[Query, Passage]], budget: Budget) -> list[Verdict]:
        verdicts: list[Verdict] = []
        with _guard_memory(), torch.inference_mode():
            for i in range(0, len(pairs), self._batch):
                budget.check()
                batch = pairs[i: i + self._batch]
                encoded = self._verifier_tokenizer(
                    [f"{p.context} | {p.text}" for _, p in batch], [q.hypothesis for q, _ in batch],
                    truncation="only_first", max_length=VERIFIER_MAX_TOKENS, padding=True,
                    return_tensors="pt").to(self._device)
                for logits in self._verifier(**encoded).logits.tolist():
                    probs = softmax(logits, self._verdict_temperature or 1.0)
                    best = max(range(len(VERDICT_LABELS)), key=probs.__getitem__)
                    verdicts.append(Verdict(
                        label=VERDICT_LABELS[best],  # type: ignore[arg-type]
                        probs={n: p for n, p in zip(VERDICT_LABELS, probs, strict=True)} if self._verdict_temperature else None,
                        source="learned"))
        return verdicts
