"""Fine-tune the verifier: a sentence-pair classifier over (passage, requirement) with five verdicts.

    PYTHONPATH=backend python -m ml.train_verifier --base-dir <local nli-distilroberta-base> \
        --splits ml/data/generated/splits --config ml/configs/verifier.json --out ml/runs/<name>

The base model's three-way NLI head is replaced by a new five-way head; the encoder is fine-tuned.
Nothing is downloaded and the test split is not read.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import torch
import torch.nn.functional as F
from app.ml.contracts import VERDICT_LABELS
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ml.encode import encode_verification
from ml.metrics import classification_report
from ml.schema import VerificationRecord, dataset_digest
from ml.split import load_split
from ml.trainer import (
    TrainConfig,
    config_dict,
    environment,
    fit,
    seed_everything,
    sha256_of_weights,
    write_run_record,
)


def predict_logits(
    model,
    tokenizer,
    records: Sequence[VerificationRecord],
    device: torch.device,
    batch_size: int,
):
    rows: list[list[float]] = []
    with torch.no_grad():
        for i in range(0, len(records), batch_size):
            features, _ = encode_verification(records[i : i + batch_size], tokenizer)
            rows += model(
                **{k: v.to(device) for k, v in features.items()}
            ).logits.tolist()
    return rows


def macro_f1(model, tokenizer, records, device, batch_size) -> float:
    rows = predict_logits(model, tokenizer, records, device, batch_size)
    pairs = [
        (r.label, VERDICT_LABELS[max(range(len(row)), key=row.__getitem__)])
        for r, row in zip(records, rows, strict=True)
    ]
    return classification_report(pairs, list(VERDICT_LABELS))["macro_f1"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--device", default="cuda" if torch.cuda.is_available() else "cpu"
    )
    args = parser.parse_args(argv)

    config = TrainConfig.load(args.config)
    seed_everything(config.seed)
    device = torch.device(args.device)
    train = load_split(args.splits, "train", "verification")
    validation = load_split(args.splits, "validation", "verification")
    if not train or not validation:
        print(
            "The splits directory needs train and validation verification records.",
            file=sys.stderr,
        )
        return 2

    tokenizer = AutoTokenizer.from_pretrained(
        args.base_dir, local_files_only=True, use_fast=True
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_dir,
        local_files_only=True,
        use_safetensors=True,
        num_labels=len(VERDICT_LABELS),
        id2label=dict(enumerate(VERDICT_LABELS)),
        label2id={n: i for i, n in enumerate(VERDICT_LABELS)},
        ignore_mismatched_sizes=True,
    ).to(device)

    counts = [sum(r.label == label for r in train) for label in VERDICT_LABELS]
    weights = torch.tensor(
        [len(train) / (len(VERDICT_LABELS) * max(1, c)) for c in counts], device=device
    )
    history: list[dict] = []

    def step_loss(batch: Sequence[VerificationRecord]) -> torch.Tensor:
        features, labels = encode_verification(batch, tokenizer)
        logits = model(**{k: v.to(device) for k, v in features.items()}).logits
        return F.cross_entropy(logits, labels.to(device), weight=weights)

    def log(entry: dict) -> None:
        history.append(entry)
        print(json.dumps(entry))

    best = fit(
        model,
        train,
        config,
        step_loss,
        lambda: macro_f1(model, tokenizer, validation, device, config.batch_size),
        log,
    )
    model.load_state_dict(best)
    out = args.out / "verifier"
    model.save_pretrained(out, safe_serialization=True)
    tokenizer.save_pretrained(out)

    files = sorted(args.splits.glob("*-verification.jsonl"))
    write_run_record(
        args.out,
        "verifier-run.json",
        {
            "model": "verifier",
            "base_dir_name": args.base_dir.name,
            "base_weights_sha256": sha256_of_weights(args.base_dir),
            "config": config_dict(config),
            "environment": environment(),
            "history": history,
            "data": {
                "digest": dataset_digest(files),
                "train_records": len(train),
                "validation_records": len(validation),
                "label_counts": dict(zip(VERDICT_LABELS, counts, strict=True)),
                "files": [p.name for p in files],
            },
        },
    )
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
