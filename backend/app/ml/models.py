"""Local model definitions and safetensors serialization."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import torch
from safetensors.torch import load_file, save_file
from torch import nn
from transformers import AutoConfig, AutoModel, AutoTokenizer

from app.ml.calibration import softmax
from app.ml.contracts import ROLE_TYPES, ROLES, TOKEN_LABELS, Mention, Passage
from app.ml.decoding import spans_from_labels, trim_span, truncate_context
from app.ml.manifest import ArtifactError

EXTRACTOR_MAX_TOKENS = 256
EXTRACTOR_WEIGHTS = "extractor.safetensors"
HEAD_CONFIG = "head_config.json"


class ExtractorNet(nn.Module):  # type: ignore[misc]  # optional torch dependency
    def __init__(self, encoder: nn.Module, hidden_size: int, dropout: float = 0.1):
        super().__init__()
        self.encoder = encoder
        self.dropout = nn.Dropout(dropout)
        self.token_head = nn.Linear(hidden_size, len(TOKEN_LABELS))
        self.role_head = nn.Sequential(
            nn.Linear(2 * hidden_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, len(ROLES)),
        )

    def encode(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        return self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state

    def token_logits(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.token_head(self.dropout(hidden))

    def role_logits(
        self, hidden: torch.Tensor, batch_index: torch.Tensor, token_index: torch.Tensor
    ) -> torch.Tensor:
        starts = hidden[batch_index, token_index]
        summary = hidden[batch_index, 0]
        return self.role_head(self.dropout(torch.cat([starts, summary], dim=-1)))


def build_extractor(base_dir: Path, *, pretrained_weights: bool) -> ExtractorNet:
    """Build the extractor around the encoder in `base_dir` (a locally provisioned base model)."""
    if pretrained_weights:
        encoder = AutoModel.from_pretrained(base_dir, local_files_only=True, use_safetensors=True)
    else:
        encoder = AutoModel.from_config(AutoConfig.from_pretrained(base_dir, local_files_only=True))
    return ExtractorNet(encoder, encoder.config.hidden_size)


def save_extractor(model: ExtractorNet, tokenizer: Any, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    model.encoder.config.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    state = {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}
    save_file(state, str(out_dir / EXTRACTOR_WEIGHTS))
    (out_dir / HEAD_CONFIG).write_text(
        json.dumps({"token_labels": list(TOKEN_LABELS), "roles": list(ROLES)}, indent=2),
        encoding="utf-8",
    )


def load_extractor(directory: Path, device: torch.device) -> tuple[ExtractorNet, object]:
    head = json.loads((directory / HEAD_CONFIG).read_text(encoding="utf-8"))
    if head["token_labels"] != list(TOKEN_LABELS) or head["roles"] != list(ROLES):
        raise ArtifactError(
            "The extractor was trained with a different label set than this application uses."
        )
    model = build_extractor(directory, pretrained_weights=False)
    model.load_state_dict(load_file(str(directory / EXTRACTOR_WEIGHTS)), strict=True)
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, use_fast=True)
    if not tokenizer.is_fast:
        raise ArtifactError(
            "The extractor needs a fast tokenizer (character offsets are required)."
        )
    return model.to(device).eval(), tokenizer


def extract_batch(
    model: ExtractorNet,
    tokenizer: Any,
    batch: Sequence[tuple[Passage, int, str]],
    device: torch.device,
    role_temperature: float | None,
) -> list[Mention]:
    """Mentions for (passage, chunk offset, chunk text) items. Used by inference and by training validation."""
    encoded = tokenizer(
        [truncate_context(p.context) for p, _, _ in batch],
        [chunk for _, _, chunk in batch],
        truncation="only_second",
        max_length=EXTRACTOR_MAX_TOKENS,
        padding=True,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    offsets = encoded.pop("offset_mapping").tolist()
    hidden = model.encode(encoded["input_ids"].to(device), encoded["attention_mask"].to(device))
    predicted = model.token_logits(hidden).argmax(-1).tolist()

    found: list[tuple[int, int, int, str, int]] = []  # (row, start, end, type, hidden token index)
    for row in range(len(batch)):
        positions = [t for t, s in enumerate(encoded.sequence_ids(row)) if s == 1]
        labels = [TOKEN_LABELS[predicted[row][t]] for t in positions]
        for span in spans_from_labels(labels, [tuple(offsets[row][t]) for t in positions]):
            start, end = trim_span(batch[row][2], span.start, span.end)
            if start < end:
                found.append((row, start, end, span.type, positions[span.first_token]))

    roles: dict[int, tuple[str, dict[str, float] | None]] = {}
    wanted = [i for i, f in enumerate(found) if f[3] in ROLE_TYPES]
    if wanted:
        logits = model.role_logits(
            hidden,
            torch.tensor([found[i][0] for i in wanted], device=device),
            torch.tensor([found[i][4] for i in wanted], device=device),
        ).tolist()
        for i, row_logits in zip(wanted, logits, strict=True):
            probs = softmax(row_logits, role_temperature or 1.0)
            best = max(range(len(ROLES)), key=probs.__getitem__)
            calibrated = (
                {r: p for r, p in zip(ROLES, probs, strict=True)} if role_temperature else None
            )
            roles[i] = (ROLES[best], calibrated)

    mentions = []
    for i, (row, start, end, kind, _) in enumerate(found):
        passage, offset, chunk = batch[row]
        role, role_probs = roles.get(i, (None, None))
        mentions.append(
            Mention(
                passage_id=passage.id,
                start=offset + start,
                end=offset + end,
                text=chunk[start:end],
                type=kind,
                role=role,
                role_probs=role_probs,
                source="learned",
            )
        )
    return mentions
