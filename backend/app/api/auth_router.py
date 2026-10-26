import hashlib

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import current_request_id, get_store
from app.api.schemas import Credentials, DeleteAccountIn, UserOut
from app.auth import service
from app.auth.deps import CSRF_COOKIE, SESSION_COOKIE, Principal, current_principal
from app.core.config import Settings, get_settings
from app.core.net import client_ip
from app.core.ratelimit import limiter
from app.db.models import User
from app.db.session import get_db
from app.documents.storage import BlobStore
from app.privacy import deletion

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, settings: Settings, session_token: str, csrf: str) -> None:
    options = {"max_age": settings.session_ttl_hours * 3600, "secure": settings.is_production,
               "samesite": "lax", "path": "/"}
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, **options)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **options)  # the SPA echoes it in X-CSRF-Token


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    body: Credentials, request: Request, response: Response,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> User:
    limiter.check(f"auth:{client_ip(request, settings)}", settings.rate_limit_auth_per_minute)
    user = service.register(db, body.email, body.password, current_request_id())
    token, csrf = service.create_session(db, settings, user)
    _set_cookies(response, settings, token, csrf)
    return user


@router.post("/login", response_model=UserOut)
def login(
    body: Credentials, request: Request, response: Response,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> User:
    ip = client_ip(request, settings)
    limiter.check(f"auth:{ip}", settings.rate_limit_auth_per_minute)
    identity = hashlib.sha256(body.email.strip().lower().encode()).hexdigest()[:16]
    limiter.check(f"login:{ip}:{identity}", max(3, settings.rate_limit_auth_per_minute // 2))
    user = service.authenticate(db, body.email, body.password, current_request_id())
    token, csrf = service.create_session(db, settings, user)
    _set_cookies(response, settings, token, csrf)
    return user


@router.post("/logout", status_code=204)
def logout(
    request: Request, _: Principal = Depends(current_principal),
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> Response:
    service.revoke_session(db, settings, request.cookies.get(SESSION_COOKIE))
    out = Response(status_code=204)
    _clear_cookies(out)
    return out


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(current_principal)) -> User:
    return principal.user


@router.post("/delete-account", status_code=204)
def delete_account(
    body: DeleteAccountIn, principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db), store: BlobStore = Depends(get_store),
) -> Response:
    """Permanently deletes the account and everything it owns. Requires the current password."""
    service.confirm_password(principal.user, body.password)
    deletion.delete_account(db, store, principal.user.id, current_request_id())
    out = Response(status_code=204)
    _clear_cookies(out)
    return out
