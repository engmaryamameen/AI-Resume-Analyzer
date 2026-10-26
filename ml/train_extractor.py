"""Fine-tune the extractor: an encoder with a span-tagging head and a mention-role head.

    PYTHONPATH=backend python -m ml.train_extractor --base-dir <local distilroberta-base> \
        --splits ml/data/generated/splits --config ml/configs/extractor.json --out ml/runs/<name>

Nothing is downloaded. `--base-dir` must hold the base model files already provisioned on this machine
(see models/README.md). The best epoch on the validation split is kept; the test split is not read.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from app.ml.contracts import ROLE_TYPES, ROLES
from app.ml.models import build_extractor, extract_batch, save_extractor
from ml.encode import IGNORE, encode_extraction
from ml.inputs import passage_of
from ml.metrics import span_scores
from ml.schema import ExtractionRecord, dataset_digest
from ml.split import load_split
from ml.trainer import TrainConfig, config_dict, environment, fit, seed_everything, sha256_of_weights, write_run_record


def predict(model, tokenizer, records: Sequence[ExtractionRecord], device: torch.device, batch_size: int):
    """Predicted (start, end, type) sets and {(start, end, type): role} maps, using the inference decoder."""
    sets, roles = [], []
    with torch.no_grad():
        for i in range(0, len(records), batch_size):
            part = records[i: i + batch_size]
            items = [(passage_of(r), 0, r.text) for r in part]
            mentions = extract_batch(model, tokenizer, items, device, None)
            for record in part:
                mine = [m for m in mentions if m.passage_id == record.id]
                sets.append({(m.start, m.end, m.type) for m in mine})
                roles.append({(m.start, m.end, m.type): m.role for m in mine})
    return sets, roles


def validation_score(model, tokenizer, records, device, batch_size) -> float:
    predicted, roles = predict(model, tokenizer, records, device, batch_size)
    gold = [{(s.start, s.end, s.type) for s in r.spans} for r in records]
    f1 = span_scores(gold, predicted)["micro"]["f1"]
    wanted = correct = 0
    for record, found in zip(records, roles, strict=True):
        for span in record.spans:
            if span.type in ROLE_TYPES:
                wanted += 1
                correct += found.get((span.start, span.end, span.type)) == span.role
    role_accuracy = correct / wanted if wanted else 0.0
    return 0.5 * f1 + 0.5 * role_accuracy


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args(argv)

    config = TrainConfig.load(args.config)
    seed_everything(config.seed)
    device = torch.device(args.device)
    train = load_split(args.splits, "train", "extraction")
    validation = load_split(args.splits, "validation", "extraction")
    if not train or not validation:
        print("The splits directory needs train and validation extraction records.", file=sys.stderr)
        return 2

    tokenizer = AutoTokenizer.from_pretrained(args.base_dir, local_files_only=True, use_fast=True)
    model = build_extractor(args.base_dir, pretrained_weights=True).to(device)
    history: list[dict] = []

    def step_loss(batch: Sequence[ExtractionRecord]) -> torch.Tensor:
        encoded = encode_extraction(batch, tokenizer)
        hidden = model.encode(encoded.input_ids.to(device), encoded.attention_mask.to(device))
        logits = model.token_logits(hidden)
        loss = F.cross_entropy(logits.flatten(0, 1), encoded.token_labels.to(device).flatten(), ignore_index=IGNORE)
        if len(encoded.role_targets):
            role_logits = model.role_logits(hidden, encoded.role_rows.to(device), encoded.role_tokens.to(device))
            loss = loss + config.head_loss_weight * F.cross_entropy(role_logits, encoded.role_targets.to(device))
        return loss

    def log(entry: dict) -> None:
        history.append(entry)
        print(json.dumps(entry))

    best = fit(model, train, config, step_loss,
               lambda: validation_score(model, tokenizer, validation, device, config.batch_size), log)
    model.load_state_dict(best)
    save_extractor(model, tokenizer, args.out / "extractor")

    files = sorted(args.splits.glob("*-extraction.jsonl"))
    write_run_record(args.out, "extractor-run.json", {
        "model": "extractor", "base_dir_name": args.base_dir.name, "base_weights_sha256": sha256_of_weights(args.base_dir),
        "config": config_dict(config), "environment": environment(), "history": history,
        "data": {"digest": dataset_digest(files), "train_records": len(train), "validation_records": len(validation),
                 "files": [p.name for p in files]},
        "roles": list(ROLES),
    })
    print(f"saved {args.out / 'extractor'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
