import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.db.models import IdempotencyKey

KEY_TTL = timedelta(hours=24)


def validate_key(key: str | None) -> str | None:
    if key is None:
        return None
    key = key.strip()
    if not (8 <= len(key) <= 128) or not key.isascii() or not all(c.isalnum() or c in "-_." for c in key):
        raise Conflict("Idempotency-Key must be 8-128 characters of letters, digits, '-', '_' or '.'.",
                       code="invalid_idempotency_key")
    return key


def claim(
    db: Session, user_id: uuid.UUID, scope: str, key: str, request_hash: str, result_id: uuid.UUID
) -> uuid.UUID | None:
    """Atomically claim an idempotency key.

    Returns None if this call now owns the key (create the object with `result_id` in the same
    transaction). Otherwise returns the id of the result created by the first call. A concurrent
    duplicate blocks on the unique index until the first transaction commits, so exactly one
    logical object is ever created. Reusing a key with a different request is a conflict.
    """
    inserted = db.execute(
        pg_insert(IdempotencyKey)
        .values(id=uuid.uuid4(), user_id=user_id, scope=scope, key=key,
                request_hash=request_hash, result_id=result_id)
        .on_conflict_do_nothing(constraint="uq_idempotency")
        .returning(IdempotencyKey.id)
    ).first()
    if inserted is not None:
        return None
    existing = db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id, IdempotencyKey.scope == scope, IdempotencyKey.key == key
        )
    ).scalar_one()
    if existing.request_hash != request_hash:
        raise Conflict("This Idempotency-Key was already used for a different request.",
                       code="idempotency_key_reused")
    return existing.result_id


def purge_expired(db: Session) -> int:
    cutoff = datetime.now(UTC) - KEY_TTL
    return db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff)).rowcount or 0
