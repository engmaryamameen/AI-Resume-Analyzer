"""Fit temperature scaling for the two heads that report probabilities, and measure calibration.

    PYTHONPATH=backend python -m ml.calibrate --run ml/runs/<name> --splits ml/data/generated/splits

The temperature is fitted on the calibration split; the reported ECE is measured on the validation split,
which the temperature never saw. The result is written to <run>/calibration.json and recorded in the model
manifest by `ml.make_manifest`. Whether probabilities are *shown* is decided at inference time by the
manifest's display policy, not here.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.ml.calibration import evaluate_calibration, fit_temperature
from app.ml.contracts import VERDICT_LABELS
from app.ml.models import load_extractor
from ml.encode import encode_extraction
from ml.schema import ExtractionRecord, VerificationRecord
from ml.split import load_split
from ml.train_verifier import predict_logits


def role_logits(model, tokenizer, records: Sequence[ExtractionRecord], device: torch.device, batch_size: int):
    """Role logits for the gold spans, so the role head is calibrated independently of span detection."""
    rows: list[list[float]] = []
    targets: list[int] = []
    with torch.no_grad():
        for i in range(0, len(records), batch_size):
            batch = encode_extraction(records[i: i + batch_size], tokenizer)
            if not len(batch.role_targets):
                continue
            hidden = model.encode(batch.input_ids.to(device), batch.attention_mask.to(device))
            rows += model.role_logits(hidden, batch.role_rows.to(device), batch.role_tokens.to(device)).tolist()
            targets += batch.role_targets.tolist()
    return rows, targets


def calibration_entry(fit_rows, fit_labels, check_rows, check_labels) -> dict:
    temperature = fit_temperature(fit_rows, fit_labels)
    checked = evaluate_calibration(check_rows, check_labels, temperature)
    return {"temperature": temperature, "validation_samples": checked.samples, "ece": checked.ece_after,
            "ece_uncalibrated": checked.ece_before, "fitted_on_samples": len(fit_labels)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)
    device = torch.device(args.device)
    result: dict[str, dict] = {}

    extractor_dir = args.run / "extractor"
    if extractor_dir.is_dir():
        model, tokenizer = load_extractor(extractor_dir, device)
        fit_rows, fit_labels = role_logits(model, tokenizer, load_split(args.splits, "calibration", "extraction"), device, args.batch_size)
        check_rows, check_labels = role_logits(model, tokenizer, load_split(args.splits, "validation", "extraction"), device, args.batch_size)
        if fit_rows and check_rows:
            result["role"] = calibration_entry(fit_rows, fit_labels, check_rows, check_labels)

    verifier_dir = args.run / "verifier"
    if verifier_dir.is_dir():
        tokenizer = AutoTokenizer.from_pretrained(verifier_dir, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            verifier_dir, local_files_only=True, use_safetensors=True).to(device).eval()
        fit_records: list[VerificationRecord] = load_split(args.splits, "calibration", "verification")  # type: ignore[assignment]
        check_records: list[VerificationRecord] = load_split(args.splits, "validation", "verification")  # type: ignore[assignment]
        if fit_records and check_records:
            fit_rows = predict_logits(model, tokenizer, fit_records, device, args.batch_size)
            check_rows = predict_logits(model, tokenizer, check_records, device, args.batch_size)
            result["verdict"] = calibration_entry(
                fit_rows, [VERDICT_LABELS.index(r.label) for r in fit_records],
                check_rows, [VERDICT_LABELS.index(r.label) for r in check_records])

    (args.run / "calibration.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
