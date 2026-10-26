"""Measure latency and memory of an engine on this machine.

    PYTHONPATH=backend python -m ml.bench --candidate ml/runs/<name> --data <extraction+verification files> --out bench.json
    PYTHONPATH=backend python -m ml.bench --engine rules --data <files> --out bench.json

Reported numbers describe the machine and settings they were measured on and nothing else. Run it on the
hardware you intend to deploy to, with the batch size and thread count you intend to use.
"""

import argparse
import json
import resource
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from app.ml.engine import Budget, Engine
from ml.inputs import passage_of, query_of
from ml.metrics import percentile
from ml.schema import ExtractionRecord, VerificationRecord, read_jsonl

REPEATS = 5
NO_TIME_LIMIT = 10**9


def _timed(call, items: int) -> dict:
    samples = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        call()
        samples.append(time.perf_counter() - started)
    return {"items": items, "runs": REPEATS, "seconds_p50": percentile(samples, 0.5), "seconds_p95": percentile(samples, 0.95),
            "seconds_per_item": percentile(samples, 0.5) / max(1, items)}


def bench(engine: Engine, extraction: Sequence[ExtractionRecord], verification: Sequence[VerificationRecord]) -> dict:
    out: dict = {}
    passages = [passage_of(r) for r in extraction]
    pairs = [(query_of(r.requirement, r.id), passage_of(r)) for r in verification]
    if passages:
        out["extract"] = _timed(lambda: engine.extract(passages, Budget(NO_TIME_LIMIT)), len(passages))
    if pairs:
        out["verify"] = _timed(lambda: engine.verify(pairs, Budget(NO_TIME_LIMIT)), len(pairs))
        queries = [q for q, _ in pairs[:20]]
        corpus = [p for _, p in pairs]
        out["retrieve"] = _timed(lambda: engine.retrieve(queries, corpus, 5, Budget(NO_TIME_LIMIT)), len(queries))
    out["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # kilobytes on Linux
    try:
        import torch

        if torch.cuda.is_available():
            out["cuda_peak_allocated_mb"] = torch.cuda.max_memory_allocated() / 2**20
    except ImportError:
        pass
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--engine", choices=["rules"])
    group.add_argument("--candidate", type=Path)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    if args.engine == "rules":
        from app.ml.rules import RulesEngine

        engine: Engine = RulesEngine()
    else:
        from ml.candidate import load_candidate_engine

        engine = load_candidate_engine(args.candidate, args.device)
    load_seconds = time.perf_counter() - started

    records = [r for path in args.data for r in read_jsonl(path)]
    result = {"engine": engine.info.model_dump(mode="json"), "device": args.device, "load_seconds": load_seconds,
              **bench(engine, [r for r in records if isinstance(r, ExtractionRecord)],
                      [r for r in records if isinstance(r, VerificationRecord)])}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
