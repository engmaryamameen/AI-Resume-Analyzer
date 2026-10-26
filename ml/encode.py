"""Tokenisation of training records. Requires torch and transformers.

Mirrors the inference code in app.ml.local: same context line, same sentence-pair layout, same
truncation sides, so a model sees at training time what it will see in production.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import torch

from app.ml.contracts import ROLE_TYPES, ROLES, TOKEN_LABELS, VERDICT_LABELS, format_context
from app.ml.decoding import truncate_context
from app.ml.local import VERIFIER_MAX_TOKENS
from app.ml.models import EXTRACTOR_MAX_TOKENS
from ml.schema import ExtractionRecord, VerificationRecord

IGNORE = -100
_LABEL_ID = {label: i for i, label in enumerate(TOKEN_LABELS)}


@dataclass
class ExtractionBatch:
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    token_labels: torch.Tensor  # (batch, seq), IGNORE outside the passage text
    role_rows: torch.Tensor  # batch index of each role target
    role_tokens: torch.Tensor  # token index of each role target (the span's first token)
    role_targets: torch.Tensor


def encode_extraction(records: Sequence[ExtractionRecord], tokenizer) -> ExtractionBatch:
    encoded = tokenizer(
        [truncate_context(format_context(r.section_kind, r.entry_header)) for r in records], [r.text for r in records],
        truncation="only_second", max_length=EXTRACTOR_MAX_TOKENS, padding=True, return_offsets_mapping=True,
        return_tensors="pt")
    offsets = encoded["offset_mapping"].tolist()
    labels = torch.full(encoded["input_ids"].shape, IGNORE, dtype=torch.long)
    rows: list[int] = []
    tokens: list[int] = []
    targets: list[int] = []
    for row, record in enumerate(records):
        sequence = encoded.sequence_ids(row)
        spans = sorted(record.spans, key=lambda s: s.start)
        for index, who in enumerate(sequence):
            if who != 1:
                continue
            start, end = offsets[row][index]
            labels[row, index] = _LABEL_ID["O"]
            for span in spans:
                if start < span.end and end > span.start:
                    first = not any(
                        sequence[j] == 1 and offsets[row][j][0] < span.end and offsets[row][j][1] > span.start
                        for j in range(index))
                    labels[row, index] = _LABEL_ID[f"{'B' if first else 'I'}-{span.type}"]
                    if first and span.type in ROLE_TYPES and span.role:
                        rows.append(row)
                        tokens.append(index)
                        targets.append(ROLES.index(span.role))
                    break
    return ExtractionBatch(
        encoded["input_ids"], encoded["attention_mask"], labels,
        torch.tensor(rows, dtype=torch.long), torch.tensor(tokens, dtype=torch.long),
        torch.tensor(targets, dtype=torch.long))


def encode_verification(records: Sequence[VerificationRecord], tokenizer) -> tuple[dict, torch.Tensor]:
    encoded = tokenizer(
        [f"{format_context(r.section_kind, r.entry_header)} | {r.text}" for r in records],
        [r.requirement.hypothesis() for r in records],
        truncation="only_first", max_length=VERIFIER_MAX_TOKENS, padding=True, return_tensors="pt")
    labels = torch.tensor([VERDICT_LABELS.index(r.label) for r in records], dtype=torch.long)
    return dict(encoded), labels
