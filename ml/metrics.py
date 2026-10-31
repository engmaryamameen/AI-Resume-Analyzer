"""Evaluation metrics. Pure Python, so they can be unit-tested without a model or a GPU."""

import math
from collections import Counter, defaultdict
from collections.abc import Hashable, Sequence


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def span_scores(
    gold: Sequence[set[tuple[int, int, str]]],
    predicted: Sequence[set[tuple[int, int, str]]],
) -> dict[str, dict[str, float]]:
    """Exact-match (start, end, type) precision/recall/F1, per entity type and micro-averaged."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for g, p in zip(gold, predicted, strict=True):
        for span in g & p:
            counts[span[2]][0] += 1
        for span in p - g:
            counts[span[2]][1] += 1
        for span in g - p:
            counts[span[2]][2] += 1
    out = {kind: prf(*c) for kind, c in sorted(counts.items())}
    total = [sum(c[i] for c in counts.values()) for i in range(3)]
    out["micro"] = prf(*total)
    return out


def confusion(
    pairs: Sequence[tuple[Hashable, Hashable]], labels: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Rows are gold labels, columns are predictions."""
    table = {g: {p: 0 for p in labels} for g in labels}
    for gold, predicted in pairs:
        table[str(gold)][str(predicted)] += 1
    return table


def classification_report(
    pairs: Sequence[tuple[str, str]], labels: Sequence[str]
) -> dict:
    table = confusion(pairs, labels)
    per_class = {}
    for label in labels:
        tp = table[label][label]
        fp = sum(table[g][label] for g in labels if g != label)
        fn = sum(table[label][p] for p in labels if p != label)
        per_class[label] = {**prf(tp, fp, fn), "support": tp + fn}
    total = len(pairs)
    correct = sum(table[label][label] for label in labels)
    present = [m for m in per_class.values() if m["support"] > 0]
    return {
        "samples": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(m["f1"] for m in present) / len(present) if present else 0.0,
        "per_class": per_class,
        "confusion": table,
    }


def retrieval_scores(
    ranked_relevance: Sequence[Sequence[bool]], ks: Sequence[int] = (1, 3)
) -> dict[str, float]:
    """`ranked_relevance[i]` lists, best first, whether each retrieved passage is relevant.

    recall@k is the share of queries with at least one relevant passage in the top k; MRR is the mean
    reciprocal rank of the first relevant passage (0 when none is retrieved)."""
    total = len(ranked_relevance)
    if not total:
        return {}
    out = {f"hit@{k}": sum(any(r[:k]) for r in ranked_relevance) / total for k in ks}
    reciprocal = [
        next((1 / (i + 1) for i, hit in enumerate(r) if hit), 0.0)
        for r in ranked_relevance
    ]
    out["mrr"] = sum(reciprocal) / total
    out["queries"] = total
    return out


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def label_counts(labels: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(labels).items()))
