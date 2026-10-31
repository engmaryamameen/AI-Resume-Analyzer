import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict


def lock_and_check_latest(
    db: Session,
    parent_model: Any,
    parent_id: uuid.UUID,
    latest_version_no: Callable[[], int],
    base_version_no: int,
) -> int:
    """Serialise writers of a versioned object and enforce optimistic concurrency.

    Versions are immutable; a change creates the next one. The parent row is locked so two concurrent
    edits cannot pick the same number, and the caller must have based its edit on the latest version.
    Returns the current latest version number.
    """
    db.execute(select(parent_model.id).where(parent_model.id == parent_id).with_for_update())
    current = latest_version_no()
    if base_version_no != current:
        raise Conflict(
            "A newer version exists. Reload and reapply your changes.",
            code="stale_base_version",
            details={"latest_version": current},
        )
    return current
