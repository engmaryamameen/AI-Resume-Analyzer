"""Probability calibration by temperature scaling, and the metrics that judge it.

Pure Python on purpose: it is small, has no dependencies, and can be unit-tested without any model.
A model's raw softmax output is not a probability in the frequentist sense; after fitting one
temperature on held-out data it is *better calibrated*, and the expected calibration error (ECE) on a
second held-out set says by how much. Probabilities are shown to users only when that evidence exists
(see DisplayPolicy in app.ml.manifest). Raw cosine similarity is never treated as a probability.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

_GOLDEN = (math.sqrt(5) - 1) / 2


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    scaled = [x / temperature for x in logits]
    peak = max(scaled)
    exps = [math.exp(x - peak) for x in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def negative_log_likelihood(
    rows: Sequence[Sequence[float]], labels: Sequence[int], temperature: float
) -> float:
    return -sum(
        math.log(max(softmax(r, temperature)[y], 1e-12)) for r, y in zip(rows, labels, strict=True)
    ) / len(rows)


def fit_temperature(rows: Sequence[Sequence[float]], labels: Sequence[int]) -> float:
    """The temperature minimising NLL on the given data (golden-section search over log T)."""
    low, high = math.log(0.05), math.log(10.0)
    a, b = high - _GOLDEN * (high - low), low + _GOLDEN * (high - low)
    fa, fb = (negative_log_likelihood(rows, labels, math.exp(x)) for x in (a, b))
    for _ in range(60):
        if fa < fb:
            high, b, fb = b, a, fa
            a = high - _GOLDEN * (high - low)
            fa = negative_log_likelihood(rows, labels, math.exp(a))
        else:
            low, a, fa = a, b, fb
            b = low + _GOLDEN * (high - low)
            fb = negative_log_likelihood(rows, labels, math.exp(b))
    return math.exp((low + high) / 2)


@dataclass(frozen=True)
class ReliabilityBin:
    low: float
    high: float
    count: int
    mean_confidence: float
    accuracy: float


def reliability_bins(
    prob_rows: Sequence[Sequence[float]], labels: Sequence[int], bins: int = 10
) -> list[ReliabilityBin]:
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for probs, label in zip(prob_rows, labels, strict=True):
        confidence = max(probs)
        index = min(int(confidence * bins), bins - 1)
        buckets[index].append((confidence, probs.index(confidence) == label))
    out = []
    for i, bucket in enumerate(buckets):
        if bucket:
            out.append(
                ReliabilityBin(
                    i / bins,
                    (i + 1) / bins,
                    len(bucket),
                    sum(c for c, _ in bucket) / len(bucket),
                    sum(ok for _, ok in bucket) / len(bucket),
                )
            )
    return out


def expected_calibration_error(
    prob_rows: Sequence[Sequence[float]], labels: Sequence[int], bins: int = 10
) -> float:
    n = len(labels)
    return sum(
        b.count / n * abs(b.accuracy - b.mean_confidence)
        for b in reliability_bins(prob_rows, labels, bins)
    )


def brier_score(prob_rows: Sequence[Sequence[float]], labels: Sequence[int]) -> float:
    total = 0.0
    for probs, label in zip(prob_rows, labels, strict=True):
        total += sum((p - (1.0 if i == label else 0.0)) ** 2 for i, p in enumerate(probs))
    return total / len(labels)


@dataclass(frozen=True)
class CalibrationResult:
    temperature: float
    samples: int
    ece_before: float
    ece_after: float
    brier_after: float


def calibrate(rows: Sequence[Sequence[float]], labels: Sequence[int]) -> CalibrationResult:
    """Fit a temperature on one split. Report ECE for a *different* split with `evaluate_calibration`."""
    temperature = fit_temperature(rows, labels)
    return evaluate_calibration(rows, labels, temperature, ece_before_rows=rows)


def evaluate_calibration(
    rows: Sequence[Sequence[float]],
    labels: Sequence[int],
    temperature: float,
    ece_before_rows: Sequence[Sequence[float]] | None = None,
) -> CalibrationResult:
    before = [softmax(r) for r in (ece_before_rows or rows)]
    after = [softmax(r, temperature) for r in rows]
    return CalibrationResult(
        temperature=temperature,
        samples=len(labels),
        ece_before=expected_calibration_error(before, labels),
        ece_after=expected_calibration_error(after, labels),
        brier_after=brier_score(after, labels),
    )
