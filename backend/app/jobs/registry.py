"""Job kinds. A job is processed in three steps so no transaction is held while work runs:

    prepare  (short transaction)  read inputs as plain data; None means "nothing to do"
    compute  (no transaction)     CPU / model work; may call ctx.heartbeat() to keep the job's lock alive
    commit   (short transaction)  write results; runs under the user's advisory lock

`on_failed` and `on_cancelled` update the target record (résumé version, analysis run) and are the only
code that does so for terminal job outcomes.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ml.engine import Engine


class Transient(Exception):
    """A failure worth retrying (timeouts, worker-side resource limits)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class JobContext:
    engine: Engine
    heartbeat: Callable[[], None]


@dataclass(frozen=True)
class JobKind:
    name: str
    prepare: Callable[[Session, uuid.UUID], Any | None]
    compute: Callable[[Any, JobContext], Any]
    commit: Callable[[Session, uuid.UUID, Any], None]
    on_failed: Callable[[Session, uuid.UUID, str], None]
    on_cancelled: Callable[[Session, uuid.UUID], None]


_KINDS: dict[str, JobKind] = {}


def register(kind: JobKind) -> None:
    _KINDS[kind.name] = kind


def get(name: str) -> JobKind:
    return _KINDS[name]
