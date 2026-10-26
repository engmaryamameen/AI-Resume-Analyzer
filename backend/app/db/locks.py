"""Lock ordering rule for the whole application.

Any transaction that locks more than one row among {user, document, version, run, job} first takes the
user's advisory lock. Worker commits, cancellations and every deletion do so, which makes their relative
order irrelevant and removes the lock-order cycles that row locks alone would allow. Transactions that
touch a single row (claiming a job, reading) do not need it.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailable

_LOCK_NOT_AVAILABLE = "55P03"


def lock_user(db: Session, user_id: uuid.UUID, timeout_ms: int = 10_000) -> None:
    """Take the per-user transaction-scoped advisory lock, waiting at most `timeout_ms`."""
    try:
        db.execute(text(f"SET LOCAL lock_timeout = {int(timeout_ms)}"))
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": str(user_id)})
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE:
            raise ServiceUnavailable(
                "Your data is being processed right now. Please try again in a few seconds.", code="user_busy"
            ) from exc
        raise
