"""Decide whether a candidate may replace the baseline, by the criteria in a policy file.

    python -m ml.compare --candidate cand.json --baseline base.json --policy ml/configs/promotion.json [--bench bench.json]

Both reports must have been produced by `ml.evaluate` on the *same* data files. A criterion whose metric
is missing from a report fails rather than passing silently. Exit status is non-zero if any criterion fails.
Passing is necessary, not sufficient: a person still reviews the report and approves the manifest entry.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def _get(report: dict, *path: str):
    value = report
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _check(name: str, candidate, requirement: str, ok) -> dict:
    return {
        "check": name,
        "candidate": candidate,
        "requirement": requirement,
        "passed": candidate is not None and bool(ok(candidate)),
    }


def compare(
    candidate: dict, baseline: dict, policy: dict, bench: dict | None = None
) -> list[dict]:
    checks: list[dict] = []
    if _get(candidate, "data", "digest") != _get(baseline, "data", "digest"):
        checks.append(
            {
                "check": "same evaluation data",
                "candidate": _get(candidate, "data", "digest"),
                "requirement": "equals the baseline's data digest",
                "passed": False,
            }
        )

    v, vp = policy.get("verification", {}), ["verification"]
    base_f1 = _get(baseline, *vp, "macro_f1")
    cand_f1 = _get(candidate, *vp, "macro_f1")
    if base_f1 is not None and cand_f1 is not None:
        checks.append(
            _check(
                "verification macro-F1 gain",
                cand_f1 - base_f1,
                f">= {v['min_macro_f1_gain']}",
                lambda x: x >= v["min_macro_f1_gain"],
            )
        )
    else:
        checks.append(
            _check("verification macro-F1 gain", None, "both reports measured", bool)
        )
    false_support = _get(candidate, *vp, "false_support_rate")
    base_false = _get(baseline, *vp, "false_support_rate")
    checks.append(
        _check(
            "false-support rate",
            false_support,
            f"<= {v['max_false_support_rate']} and not above the baseline ({base_false})",
            lambda x: (
                x <= v["max_false_support_rate"]
                and (base_false is None or x <= base_false)
            ),
        )
    )
    checks.append(
        _check(
            "contradictions read as support",
            _get(candidate, *vp, "contradiction_read_as_support"),
            f"<= {v['max_contradiction_read_as_support']}",
            lambda x: x <= v["max_contradiction_read_as_support"],
        )
    )

    e = policy.get("extraction", {})
    cand_micro, base_micro = (
        _get(candidate, "extraction", "spans", "micro", "f1"),
        _get(baseline, "extraction", "spans", "micro", "f1"),
    )
    if cand_micro is not None and base_micro is not None:
        checks.append(
            _check(
                "extraction micro-F1 gain",
                cand_micro - base_micro,
                f">= {e['min_micro_f1_gain']}",
                lambda x: x >= e["min_micro_f1_gain"],
            )
        )
    else:
        checks.append(
            _check("extraction micro-F1 gain", None, "both reports measured", bool)
        )
    for tag, base_tag in (_get(baseline, "extraction", "spans_by_tag") or {}).items():
        cand_tag = (_get(candidate, "extraction", "spans_by_tag") or {}).get(tag)
        checks.append(
            _check(
                f"extraction F1 on '{tag}' examples",
                None if cand_tag is None else cand_tag["f1"] - base_tag["f1"],
                f">= -{e['max_regression_by_tag']}",
                lambda x: x >= -e["max_regression_by_tag"],
            )
        )

    r = policy.get("retrieval", {})
    cand_mrr, base_mrr = (
        _get(candidate, "retrieval", "mrr"),
        _get(baseline, "retrieval", "mrr"),
    )
    checks.append(
        _check(
            "retrieval MRR gain",
            None if cand_mrr is None or base_mrr is None else cand_mrr - base_mrr,
            f">= {r['min_mrr_gain']}",
            lambda x: x >= r["min_mrr_gain"],
        )
    )

    limit = policy.get("calibration", {})["max_ece"]
    checks.append(
        _check(
            "verdict ECE",
            _get(candidate, "verification", "ece"),
            f"<= {limit}",
            lambda x: x <= limit,
        )
    )
    checks.append(
        _check(
            "role ECE",
            _get(candidate, "extraction", "role_ece"),
            f"<= {limit}",
            lambda x: x <= limit,
        )
    )

    if bench is not None:
        lat = policy.get("latency", {})
        checks.append(
            _check(
                "extraction seconds per passage",
                _get(bench, "extract", "seconds_per_item"),
                f"<= {lat['max_extract_seconds_per_passage']}",
                lambda x: x <= lat["max_extract_seconds_per_passage"],
            )
        )
        checks.append(
            _check(
                "verification seconds per pair",
                _get(bench, "verify", "seconds_per_item"),
                f"<= {lat['max_verify_seconds_per_pair']}",
                lambda x: x <= lat["max_verify_seconds_per_pair"],
            )
        )
    return checks


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--bench", type=Path)
    args = parser.parse_args(argv)
    checks = compare(
        _load(args.candidate),
        _load(args.baseline),
        _load(args.policy),
        _load(args.bench) if args.bench else None,
    )
    for c in checks:
        print(
            f"{'PASS' if c['passed'] else 'FAIL'}  {c['check']}: {c['candidate']} (needs {c['requirement']})"
        )
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
