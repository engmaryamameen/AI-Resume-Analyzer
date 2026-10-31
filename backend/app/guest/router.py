"""One private, worker-processed guest analysis per network per rolling 24 hours.

Only keyed HMACs of network addresses are stored. Guest cookies authorize their own report, never the
account API. A quota reservation is serialized in PostgreSQL, persists across API restarts and is not
removed when the visitor deletes their documents. Failed extraction/analysis restores the allowance.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.analysis import job_descriptions
from app.analysis import service as analyses
from app.api.analyses_router import get_analysis
from app.api.deps import get_store
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, NotFound, RateLimited, ValidationFailed
from app.core.net import client_ip
from app.core.ratelimit import limiter
from app.core.security import constant_time_equal, hash_token
from app.db.locks import lock_user
from app.db.models import AnalysisRun, GuestAllowance, GuestAnalysis, ResumeVersion, User
from app.db.session import get_db
from app.documents import service as documents
from app.documents.storage import BlobStore
from app.documents.validation import validate_upload
from app.privacy.deletion import delete_account

router = APIRouter(prefix="/guest", tags=["guest"])
COOKIE = "mn_guest"
WINDOW = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(UTC)


def _network(request: Request, settings: Settings) -> str:
    return hash_token("guest-network:" + client_ip(request, settings), settings.secret_key)


def _origin(request: Request, settings: Settings) -> None:
    if request.headers.get("origin") not in settings.cors_origins:
        raise Forbidden("Use the form on this site to start an analysis.", code="guest_origin")


def _lock(db: Session, key: str) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(bytes.fromhex(key)[:8], signed=True)},
    )


def _visitor(db: Session, request: Request, settings: Settings) -> GuestAnalysis | None:
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        return None
    return db.execute(
        select(GuestAnalysis).where(
            GuestAnalysis.token_hash == hash_token(token, settings.secret_key),
            GuestAnalysis.expires_at > _now(),
        )
    ).scalar_one_or_none()


def _state(
    db: Session,
    guest: GuestAnalysis | None,
    network: str,
    settings: Settings,
    *,
    advance: bool = False,
) -> dict[str, Any]:
    allowance = db.get(GuestAllowance, network)
    state: dict[str, Any] = {
        "available": allowance is None or allowance.next_allowed_at <= _now(),
        "next_allowed_at": allowance.next_allowed_at
        if allowance and allowance.next_allowed_at > _now()
        else None,
        "status": "idle",
        "report": None,
        "error_code": None,
    }
    if guest is None:
        return state
    resume = db.get(ResumeVersion, guest.resume_version_id) if guest.resume_version_id else None
    if resume is None:
        state["status"] = "preparing"
        if guest.created_at < _now() - timedelta(minutes=5):
            _lock(db, guest.network_key)
            alive = db.scalar(select(GuestAnalysis.id).where(GuestAnalysis.id == guest.id))
            original = (
                db.get(GuestAllowance, guest.network_key, populate_existing=True) if alive else None
            )
            if original:
                original.next_allowed_at = _now()
                db.commit()
            state.update(
                status="failed",
                error_code="guest_interrupted",
                available=True,
                next_allowed_at=None,
            )
        return state
    if resume.status == "failed":
        state.update(status="failed", error_code=resume.error_code)
    elif resume.status == "processing":
        state["status"] = "extracting"
    elif guest.jd_version_id:
        run = db.execute(
            select(AnalysisRun).where(AnalysisRun.user_id == guest.user_id)
        ).scalar_one_or_none()
        if run is None and advance:
            run = analyses.create_analysis(
                db, settings, guest.user_id, resume.id, guest.jd_version_id, f"guest-{guest.id}"
            )
        state["status"] = "analyzing"
        if run and run.status == "failed":
            state.update(status="failed", error_code=run.error_code)
        elif run and run.status == "succeeded":
            owner = db.get(User, guest.user_id)
            if owner:
                state.update(
                    status="succeeded",
                    report=get_analysis(run.id, user=owner, db=db, settings=settings).model_dump(
                        mode="json"
                    ),
                )
    if state["status"] == "failed":
        _lock(db, guest.network_key)
        alive = db.scalar(select(GuestAnalysis.id).where(GuestAnalysis.id == guest.id))
        original = (
            db.get(GuestAllowance, guest.network_key, populate_existing=True) if alive else None
        )
        if original:
            original.next_allowed_at = _now()
        db.commit()
        state.update(available=True, next_allowed_at=None)
    return state


@router.get("")
def status(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    return _state(db, _visitor(db, request, settings), _network(request, settings), settings)


@router.post("/progress")
def progress(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    _origin(request, settings)
    guest = _visitor(db, request, settings)
    if guest is None:
        raise NotFound("This guest report has expired or is unavailable.")
    return _state(db, guest, _network(request, settings), settings, advance=True)


@router.post("/analyze", status_code=202)
def start(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    job_text: str = Form(...),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: BlobStore = Depends(get_store),
) -> dict[str, Any]:
    _origin(request, settings)
    network = _network(request, settings)
    limiter.check(f"guest-upload:{network}", settings.rate_limit_upload_per_minute)
    if len(idempotency_key) < 16 or len(idempotency_key) > 128:
        raise ValidationFailed("A valid request key is required.")
    cleaned = job_descriptions.clean_text(job_text, settings)
    upload = validate_upload(
        file.filename, file.file.read(settings.max_upload_bytes + 1), settings.max_upload_bytes
    )
    fingerprint = hashlib.sha256(
        upload.data + cleaned.encode() + idempotency_key.encode()
    ).hexdigest()
    token = hash_token("guest-report:" + idempotency_key, settings.secret_key)
    token_hash = hash_token(token, settings.secret_key)
    _lock(db, network)
    allowance = db.get(GuestAllowance, network)
    existing = db.execute(
        select(GuestAnalysis)
        .where(GuestAnalysis.network_key == network, GuestAnalysis.expires_at > _now())
        .order_by(GuestAnalysis.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if allowance and allowance.next_allowed_at > _now():
        if (
            not existing
            or not constant_time_equal(existing.token_hash, token_hash)
            or not constant_time_equal(existing.request_hash, fingerprint)
        ):
            raise RateLimited(
                "Your free analysis has been used. Create an account or return in 24 hours.",
                code="guest_limit",
                details={"next_allowed_at": allowance.next_allowed_at.isoformat()},
            )
        guest = existing
        db.rollback()
    else:
        expired_keys: list[str | None] = []
        prior = (
            db.execute(select(GuestAnalysis).where(GuestAnalysis.network_key == network))
            .scalars()
            .all()
        )
        for item in prior:
            lock_user(db, item.user_id)
            expired_keys.extend(
                db.execute(
                    select(ResumeVersion.storage_key).where(
                        ResumeVersion.user_id == item.user_id,
                        ResumeVersion.storage_key.is_not(None),
                    )
                ).scalars()
            )
            db.execute(delete(User).where(User.id == item.user_id))
        owner_id = uuid.uuid4()
        # This non-login principal owns transient rows; no account credentials or auth session are issued.
        db.add(
            User(
                id=owner_id,
                email=f"{owner_id}@guest.invalid",
                password_hash="!guest-no-login",  # noqa: S106 - invalid hash, cannot authenticate
            )
        )
        db.flush()
        guest = GuestAnalysis(
            network_key=network,
            token_hash=token_hash,
            request_hash=fingerprint,
            user_id=owner_id,
            expires_at=_now() + WINDOW,
        )
        db.add(guest)
        if allowance:
            allowance.next_allowed_at = _now() + WINDOW
        else:
            db.add(GuestAllowance(network_key=network, next_allowed_at=_now() + WINDOW))
        db.commit()
        for key in expired_keys:
            if key:
                store.delete(key)
        try:
            _, resume = documents.ingest_upload(db, store, settings, owner_id, upload, uuid.uuid4())
            _, job, _ = job_descriptions.create_job(
                db, settings, owner_id, "Guest target role", cleaned
            )
            guest.resume_version_id, guest.jd_version_id = resume.id, job.id
            db.commit()
        except Exception:
            db.rollback()
            current = db.get(GuestAllowance, network)
            if current:
                current.next_allowed_at = _now()
                db.commit()
            delete_account(db, store, owner_id, None)
            raise
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(WINDOW.total_seconds()),
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
        path="/api/v1/guest",
    )
    return _state(db, guest, network, settings)


@router.delete("", status_code=204)
def remove(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: BlobStore = Depends(get_store),
) -> Response:
    _origin(request, settings)
    guest = _visitor(db, request, settings)
    if guest:
        delete_account(db, store, guest.user_id, None)
    response.delete_cookie(COOKIE, path="/api/v1/guest")
    response.status_code = 204
    return response
