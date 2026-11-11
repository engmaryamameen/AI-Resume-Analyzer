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


@pytest.mark.parametrize("kind", ["resume", "job"])
def test_retention_rechecks_an_intervening_revision_under_the_deletion_lock(
    db_engine, tmp_path, monkeypatch, kind
):
    from app.db.locks import lock_user
    from app.db.models import JobDescription, JobDescriptionVersion, ResumeVersion
    from app.privacy import deletion

    owner, document_id = uuid.uuid4(), uuid.uuid4()
    old = datetime.now(UTC) - timedelta(days=100)
    with session_scope() as db:
        db.add(User(id=owner, email="revised@example.test", password_hash="!test"))
        db.flush()
        if kind == "resume":
            db.add(ResumeDocument(id=document_id, user_id=owner, title="Resume", created_at=old))
            db.flush()
            db.add(
                ResumeVersion(
                    document_id=document_id,
                    user_id=owner,
                    version_no=1,
                    source="upload",
                    status="ready",
                    created_at=old,
                )
            )
        else:
            db.add(JobDescription(id=document_id, user_id=owner, title="Role", created_at=old))
            db.flush()
            db.add(
                JobDescriptionVersion(
                    job_id=document_id,
                    user_id=owner,
                    version_no=1,
                    source="paste",
                    raw_text="Old role description",
                    created_at=old,
                )
            )
    original = deletion.delete_resume if kind == "resume" else deletion.delete_job_description

    def revise_before_delete(*args, **kwargs):
        # Only control the interleaving: both the revision and deletion use real transactions/locks.
        with session_scope() as revision:
            lock_user(revision, owner)
            if kind == "resume":
                revision.add(
                    ResumeVersion(
                        document_id=document_id,
                        user_id=owner,
                        version_no=2,
                        source="user_correction",
                        status="ready",
                    )
                )
            else:
                revision.add(
                    JobDescriptionVersion(
                        job_id=document_id,
                        user_id=owner,
                        version_no=2,
                        source="user_correction",
                        raw_text="Current role description",
                    )
                )
        return original(*args, **kwargs)

    monkeypatch.setattr(
        deletion,
        "delete_resume" if kind == "resume" else "delete_job_description",
        revise_before_delete,
    )
    with session_scope() as db:
        counts = expire_old_data(db, LocalPrivateStore(tmp_path / "store"), 90)
        assert counts["resumes" if kind == "resume" else "job_descriptions"] == 0
    with session_scope() as db:
        model, column = (
            (ResumeVersion, ResumeVersion.document_id)
            if kind == "resume"
            else (JobDescriptionVersion, JobDescriptionVersion.job_id)
        )
        assert db.scalar(select(func.count()).select_from(model).where(column == document_id)) == 2
