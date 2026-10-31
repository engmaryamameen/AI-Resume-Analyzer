"""The inference seam: everything the analysis pipeline needs from "the models".

Two implementations satisfy `Engine`:
  * LocalEngine (app.ml.local): locally executed neural models, loaded from approved, checksum-verified
    artifacts. Used only when all of them are provisioned and loadable.
  * RulesEngine (app.ml.rules): a deterministic baseline built on the vocabulary and cue lists. It is NOT
    machine learning, is labelled as such everywhere it is reported, and exists so the application stays
    useful when model artifacts are missing and so the models have a baseline to beat.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger
from app.ml.contracts import Candidate, EngineInfo, Mention, Passage, Query, Verdict

log = get_logger(__name__)
_HEARTBEAT_EVERY_SECONDS = 15.0


class BudgetExceeded(Exception):
    """The analysis ran out of its time budget; the caller falls back to the rules engine."""


class EngineUnavailable(Exception):
    """The learned engine cannot run (out of memory, device error, bad artifact)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Budget:
    seconds: float
    heartbeat: Callable[[], None] = lambda: None
    _started: float = field(default_factory=time.monotonic, init=False)
    _last_beat: float = field(default_factory=time.monotonic, init=False)

    def check(self) -> None:
        now = time.monotonic()
        if now - self._started > self.seconds:
            raise BudgetExceeded
        if now - self._last_beat > _HEARTBEAT_EVERY_SECONDS:
            self._last_beat = now
            self.heartbeat()


class Engine(Protocol):
    info: EngineInfo

    def extract(self, passages: Sequence[Passage], budget: Budget) -> list[Mention]: ...

    def retrieve(
        self, queries: Sequence[Query], passages: Sequence[Passage], k: int, budget: Budget
    ) -> dict[str, list[Candidate]]: ...

    def verify(self, pairs: Sequence[tuple[Query, Passage]], budget: Budget) -> list[Verdict]: ...


def load_engine(settings: Settings) -> Engine:
    """Called once when the worker starts. Never downloads anything: it reads only approved local files."""
    from app.ml.rules import RulesEngine

    if not settings.ml_enabled:
        return RulesEngine(notes=["Learned models are disabled (ML_ENABLED=false)."])
    try:
        if (settings.model_dir / "semantic-manifest.json").is_file():
            from app.ml.semantic import SemanticEngine

            return SemanticEngine.load(settings)
        from app.ml.local import LocalEngine

        return LocalEngine.load(settings)
    except Exception as exc:  # noqa: BLE001 - any load problem means "run in rules mode, and say why"
        reason = getattr(exc, "reason", None) or f"{type(exc).__name__}: {exc}"
        log.warning("learned_engine_unavailable", extra={"reason": str(reason)[:300]})
        return RulesEngine(notes=[f"Learned models are not in use: {str(reason)[:300]}"])
