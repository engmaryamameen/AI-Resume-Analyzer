"""Offline smoke check for the provisioned semantic inference profile."""

import json
import time

from app.core.config import get_settings
from app.ml.contracts import Passage, Query
from app.ml.engine import Budget, load_engine


def main() -> None:
    started = time.monotonic()
    engine = load_engine(get_settings())
    if engine.info.mode != "semantic":
        raise SystemExit("Semantic inference unavailable: " + "; ".join(engine.info.notes))
    query = Query(
        id="python",
        retrieval_query="Building backend services with Python",
        hypothesis="The candidate has hands-on experience with Python.",
    )
    passages = [
        Passage(
            id="used",
            text="Built and maintained backend services in Python for billing operations.",
            context="experience",
            section_kind="experience",
        ),
        Passage(
            id="unrelated",
            text="Organized office events and managed catering suppliers.",
            context="experience",
            section_kind="experience",
        ),
        Passage(
            id="negated",
            text="I have never used Python and have no Python experience.",
            context="experience",
            section_kind="experience",
        ),
    ]
    budget = Budget(seconds=120)
    ranked = engine.retrieve([query], passages, 3, budget)[query.id]
    verdicts = engine.verify([(query, passage) for passage in passages], budget)
    if ranked[0].passage_id != "used" or [v.label for v in verdicts] != [
        "supports",
        "unrelated",
        "contradicts",
    ]:
        raise SystemExit("Semantic smoke check failed: " + str([(v.label) for v in verdicts]))
    if any(v.probs is not None for v in verdicts):
        raise SystemExit("Uncalibrated probabilities must not be displayed")
    print(
        json.dumps(
            {
                "mode": engine.info.mode,
                "models": [m.model_dump() for m in engine.info.models],
                "checks": [
                    "semantic retrieval",
                    "support",
                    "unrelated",
                    "negation",
                    "no probability estimates",
                ],
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
        )
    )


if __name__ == "__main__":
    main()
