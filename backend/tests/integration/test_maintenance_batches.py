"""Retention drains a bounded batch and leaves the remainder for the next run."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.models import ResumeDocument, User
from app.db.session import session_scope
from app.documents.storage import LocalPrivateStore
from app.maintenance import MAINTENANCE_BATCH, expire_old_data

pytestmark = pytest.mark.integration


def test_retention_is_bounded_and_can_resume(db_engine, tmp_path):
    owner = uuid.uuid4()
    with session_scope() as db:
        db.add(User(id=owner, email="retention@example.test", password_hash="!test"))
        db.flush()
        db.add_all(
            [
                ResumeDocument(
                    user_id=owner,
                    title="Old resume",
                    created_at=datetime.now(UTC) - timedelta(days=100),
                )
                for _ in range(MAINTENANCE_BATCH + 1)
            ]
        )
    store = LocalPrivateStore(tmp_path / "storage")
    with session_scope() as db:
        result = expire_old_data(db, store, 90)
        assert result["resumes"] == MAINTENANCE_BATCH
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(ResumeDocument)) == 1
        assert expire_old_data(db, store, 90)["resumes"] == 1
