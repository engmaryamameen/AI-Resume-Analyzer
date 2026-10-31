"""Résumé ingestion, extraction jobs and versioning."""

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFound, ValidationFailed
from app.core.metrics import EXTRACTION_RESULTS
from app.db.models import ResumeDocument, ResumeVersion
from app.db.versioning import lock_and_check_latest
from app.documents.isolated import ExtractionFailed, run_extraction
from app.documents.normalize import derive_structure, normalize
from app.documents.parseability import assess
from app.documents.schema import Block, ContactField, NormalizedDocument
from app.documents.storage import BlobStore, LocalPrivateStore
from app.documents.validation import ValidatedUpload
from app.jobs import queue
from app.jobs.registry import JobContext, Transient

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def ingest_upload(
    db: Session,
    store: BlobStore,
    settings: Settings,
    user_id: uuid.UUID,
    upload: ValidatedUpload,
    document_id: uuid.UUID,
) -> tuple[ResumeDocument, ResumeVersion]:
    """Create document + version 1 + queued extraction job in one transaction.

    The blob is written first and removed again if the transaction fails. An idempotency-key claim made
    earlier in this session commits or rolls back together with it.
    """
    key = store.put(upload.data)
    try:
        document = ResumeDocument(id=document_id, user_id=user_id, title=upload.display_title)
        db.add(document)
        db.flush()
        version = ResumeVersion(
            document_id=document.id,
            user_id=user_id,
            version_no=1,
            source="upload",
            status="processing",
            storage_key=key,
            original_ext=upload.kind,
            sha256=hashlib.sha256(upload.data).hexdigest(),
            size_bytes=len(upload.data),
        )
        db.add(version)
        db.flush()
        queue.enqueue(
            db,
            user_id=user_id,
            kind="extract_resume",
            target_id=version.id,
            max_attempts=settings.job_max_attempts,
        )
        db.commit()
        return document, version
    except Exception:
        db.rollback()
        store.delete(key)
        raise


@dataclass(frozen=True)
class ExtractionWork:
    storage_key: str
    kind: str


@dataclass(frozen=True)
class ExtractionOutcome:
    normalized: dict[str, Any] | None
    parseability: dict[str, Any] | None
    error_code: str | None


def prepare_extraction(db: Session, version_id: uuid.UUID) -> ExtractionWork | None:
    version = db.get(ResumeVersion, version_id)
    if version is None or version.status != "processing" or not version.storage_key:
        return None
    return ExtractionWork(version.storage_key, version.original_ext or "")


def compute_extraction(work: ExtractionWork, _: JobContext) -> ExtractionOutcome:
    store = LocalPrivateStore(get_settings().storage_dir)
    try:
        raw = run_extraction(store.path(work.storage_key), work.kind)
    except ExtractionFailed as exc:
        if exc.code == "extraction_unavailable":
            raise Transient(exc.code) from exc
        return ExtractionOutcome(None, None, exc.code)
    if not raw.lines:
        return ExtractionOutcome(
            None, None, "no_extractable_text"
        )  # scanned/image-only: never invent text
    document = normalize(raw.lines, raw.page_count)
    parse = assess([line.text for line in raw.lines], document)
    return ExtractionOutcome(document.model_dump(mode="json"), parse.model_dump(mode="json"), None)


def commit_extraction(db: Session, version_id: uuid.UUID, outcome: ExtractionOutcome) -> None:
    version = db.execute(
        select(ResumeVersion).where(ResumeVersion.id == version_id).with_for_update()
    ).scalar_one_or_none()
    if version is None or version.status != "processing":
        return
    if outcome.error_code:
        version.status, version.error_code = "failed", outcome.error_code
        EXTRACTION_RESULTS.labels(outcome="failed").inc()
        return
    version.normalized, version.parseability = outcome.normalized, outcome.parseability
    version.status, version.error_code = "ready", None
    reliable = (outcome.parseability or {}).get("reliable_for_analysis")
    EXTRACTION_RESULTS.labels(outcome="ready" if reliable else "low_confidence").inc()


def fail_extraction(db: Session, version_id: uuid.UUID, code: str) -> None:
    version = db.get(ResumeVersion, version_id)
    if version is not None and version.status == "processing":
        version.status, version.error_code = "failed", code[:64]
        EXTRACTION_RESULTS.labels(outcome="failed").inc()


def get_document(db: Session, user_id: uuid.UUID, document_id: uuid.UUID) -> ResumeDocument:
    document = db.execute(
        select(ResumeDocument).where(
            ResumeDocument.id == document_id, ResumeDocument.user_id == user_id
        )
    ).scalar_one_or_none()
    if document is None:
        raise NotFound("Résumé not found.")
    return document


def get_version(
    db: Session, user_id: uuid.UUID, document_id: uuid.UUID, version_no: int | None = None
) -> ResumeVersion:
    query = select(ResumeVersion).where(
        ResumeVersion.document_id == document_id, ResumeVersion.user_id == user_id
    )
    query = (
        query.where(ResumeVersion.version_no == version_no)
        if version_no
        else query.order_by(ResumeVersion.version_no.desc()).limit(1)
    )
    version = db.execute(query).scalar_one_or_none()
    if version is None:
        raise NotFound("Résumé version not found.")
    return version


def get_version_by_id(db: Session, user_id: uuid.UUID, version_id: uuid.UUID) -> ResumeVersion:
    version = db.execute(
        select(ResumeVersion).where(
            ResumeVersion.id == version_id, ResumeVersion.user_id == user_id
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("Résumé version not found.")
    return version


def latest_version_no(db: Session, document_id: uuid.UUID) -> int:
    return db.execute(
        select(func.coalesce(func.max(ResumeVersion.version_no), 0)).where(
            ResumeVersion.document_id == document_id
        )
    ).scalar_one()


def create_corrected_version(
    db: Session,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    base: ResumeVersion,
    block_edits: dict[str, str],
    contact: dict[str, str | None],
) -> ResumeVersion:
    """Save user corrections as the next immutable version.

    Block edits change derived facts (dates, experience, entries), so structure is re-derived from the
    edited blocks and parseability is re-assessed; nothing derived is carried over stale.
    """
    if base.status != "ready" or base.normalized is None:
        raise ValidationFailed(
            "Only a successfully read résumé can be corrected.", code="version_not_ready"
        )
    document = NormalizedDocument.model_validate(base.normalized)
    edited = derive_structure(_apply_corrections(document, block_edits, contact), date.today())
    parse = assess([b.text for b in edited.blocks], edited)

    current = lock_and_check_latest(
        db, ResumeDocument, document_id, lambda: latest_version_no(db, document_id), base.version_no
    )
    version = ResumeVersion(
        document_id=document_id,
        user_id=user_id,
        version_no=current + 1,
        source="user_correction",
        status="ready",
        original_ext=base.original_ext,
        normalized=edited.model_dump(mode="json"),
        parseability=parse.model_dump(mode="json"),
    )
    db.add(version)
    db.flush()
    return version


def _apply_corrections(
    document: NormalizedDocument, block_edits: dict[str, str], contact: dict[str, str | None]
) -> NormalizedDocument:
    known = {b.id for b in document.blocks}
    unknown = sorted(set(block_edits) - known)
    if unknown:
        raise ValidationFailed(
            "Some blocks do not exist in this version.",
            code="unknown_block",
            details={"block_ids": unknown[:10]},
        )
    blocks: list[Block] = []
    for block in document.blocks:
        if block.id in block_edits:
            text = block_edits[block.id].strip()
            if not text:
                raise ValidationFailed("A corrected line can't be empty.", code="empty_text")
            block = block.model_copy(update={"text": text[:4000]})
        blocks.append(block)

    fields: dict[str, ContactField] = {}
    for key in ("name", "email", "phone"):
        if key not in contact:
            continue
        value = (contact[key] or "").strip()[:200] or None
        if key == "email" and value and not _EMAIL_RE.match(value):
            raise ValidationFailed("Enter a valid email address.", code="invalid_email")
        fields[key] = ContactField(
            value=value, confidence="high", block_id=getattr(document.contact, key).block_id
        )
    return document.model_copy(
        update={"blocks": blocks, "contact": document.contact.model_copy(update=fields)}
    )
