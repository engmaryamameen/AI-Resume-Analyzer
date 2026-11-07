import hashlib
import uuid
from typing import Literal, TypedDict

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import current_request_id, get_store
from app.api.schemas import (
    AccountPasswordIn,
    Credentials,
    DeleteAccountIn,
    EmailRequest,
    RegistrationOut,
    SessionOut,
    UserOut,
)
from app.auth import lifecycle, service
from app.auth.deps import CSRF_COOKIE, SESSION_COOKIE, Principal, current_principal
from app.core.config import Settings, get_settings
from app.core.errors import Conflict
from app.core.net import client_ip
from app.core.ratelimit import limiter
from app.core.security import normalise_email
from app.db.models import AuditEvent, User
from app.db.models import Session as AuthSession
from app.db.session import get_db
from app.documents.storage import BlobStore
from app.privacy import deletion

router = APIRouter(prefix="/auth", tags=["auth"])


class CookieOptions(TypedDict):
    max_age: int
    secure: bool
    samesite: Literal["lax"]
    path: str


def _set_cookies(response: Response, settings: Settings, session_token: str, csrf: str) -> None:
    options: CookieOptions = {
        "max_age": settings.session_ttl_hours * 3600,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, **options)
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, **options
    )  # the SPA echoes it in X-CSRF-Token


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/register", response_model=RegistrationOut, status_code=201)
def register(
    body: Credentials,
    background: BackgroundTasks,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RegistrationOut:
    limiter.check(f"auth:{client_ip(request, settings)}", settings.rate_limit_auth_per_minute)
    if settings.email_verification_required:
        lifecycle.require_delivery(settings)
    try:
        user = service.register(db, body.email, body.password, current_request_id())
    except Conflict as exc:
        if not settings.email_verification_required or exc.code != "email_taken":
            raise
        user = None
    if settings.email_verification_required:
        # Public registration never creates a session or exposes whether an account exists.
        # Registration does not change existing credentials; mailbox confirmation establishes them.
        db.commit()
        address = normalise_email(body.email)
        background.add_task(lifecycle.send_account_link, settings, address, "verify_email")
        return RegistrationOut(user=None, email_verification_required=True)
    assert user is not None
    token, csrf = service.create_session(db, settings, user)
    _set_cookies(response, settings, token, csrf)
    return RegistrationOut(user=_user_out(user, settings), email_verification_required=False)


@router.post("/login", response_model=UserOut)
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    ip = client_ip(request, settings)
    limiter.check(f"auth:{ip}", settings.rate_limit_auth_per_minute)
    identity = hashlib.sha256(body.email.strip().lower().encode()).hexdigest()[:16]
    limiter.check(f"login:{ip}:{identity}", max(3, settings.rate_limit_auth_per_minute // 2))
    user = service.authenticate(db, body.email, body.password, current_request_id())
    token, csrf = service.create_session(db, settings, user)
    _set_cookies(response, settings, token, csrf)
    return _user_out(user, settings)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    _: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    service.revoke_session(db, settings, request.cookies.get(SESSION_COOKIE))
    out = Response(status_code=204)
    _clear_cookies(out)
    return out


@router.get("/me", response_model=UserOut)
def me(
    principal: Principal = Depends(current_principal), settings: Settings = Depends(get_settings)
) -> UserOut:
    return _user_out(principal.user, settings)


@router.post("/delete-account", status_code=204)
def delete_account(
    body: DeleteAccountIn,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
    store: BlobStore = Depends(get_store),
) -> Response:
    """Permanently deletes the account and everything it owns. Requires the current password."""
    service.confirm_password(principal.user, body.password)
    deletion.delete_account(db, store, principal.user.id, current_request_id())
    out = Response(status_code=204)
    _clear_cookies(out)
    return out


def _user_out(user: User, settings: Settings) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        email_verified_at=user.email_verified_at,
        email_verification_required=settings.email_verification_required,
    )


def _email_request(
    body: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    settings: Settings,
    purpose: lifecycle.Purpose,
) -> Response:
    limiter.check(f"email:{client_ip(request, settings)}", settings.rate_limit_auth_per_minute)
    identity = hashlib.sha256(body.email.strip().lower().encode()).hexdigest()
    limiter.check(f"email:{purpose}:{identity}", 3)
    lifecycle.require_delivery(settings)
    background.add_task(lifecycle.send_account_link, settings, body.email, purpose)
    return Response(status_code=204)


@router.post("/forgot-password", status_code=204)
def forgot_password(
    body: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> Response:
    return _email_request(body, request, background, settings, "reset_password")


@router.post("/request-verification", status_code=204)
def request_verification(
    body: EmailRequest,
    request: Request,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> Response:
    return _email_request(body, request, background, settings, "verify_email")


@router.post("/verify-email", status_code=204)
def verify_email(
    body: AccountPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    limiter.check(f"token:{client_ip(request, settings)}", settings.rate_limit_auth_per_minute)
    lifecycle.consume_token(db, settings, body.token, "verify_email", body.password)
    out = Response(status_code=204)
    _clear_cookies(out)
    return out


@router.post("/reset-password", status_code=204)
def reset_password(
    body: AccountPasswordIn,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    limiter.check(f"token:{client_ip(request, settings)}", settings.rate_limit_auth_per_minute)
    user = lifecycle.consume_token(db, settings, body.token, "reset_password", body.password)
    background.add_task(lifecycle.notify_password_reset, settings, user.email)
    out = Response(status_code=204)
    _clear_cookies(out)
    return out


@router.get("/sessions", response_model=list[SessionOut])
def sessions(
    principal: Principal = Depends(current_principal), db: Session = Depends(get_db)
) -> list[SessionOut]:
    from datetime import UTC, datetime

    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == principal.user.id, AuthSession.expires_at > datetime.now(UTC))
        .order_by(AuthSession.created_at.desc())
    ).all()
    return [
        SessionOut(
            id=row.id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            current=row.id == principal.session.id,
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_device(
    session_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        delete(AuthSession).where(
            AuthSession.id == session_id, AuthSession.user_id == principal.user.id
        )
    )
    db.add(AuditEvent(user_id=principal.user.id, action="session.revoked"))
    db.commit()
    out = Response(status_code=204)
    if session_id == principal.session.id:
        _clear_cookies(out)
    return out
