"""Authentication, CSRF and role dependencies. Routers depend on these and hold no auth logic."""

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import service
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, Unauthenticated
from app.core.ratelimit import limiter
from app.core.security import constant_time_equal, hash_token
from app.db.models import Session as AuthSession
from app.db.models import User
from app.db.session import get_db

SESSION_COOKIE = "rs_session"
CSRF_COOKIE = "rs_csrf"
CSRF_HEADER = "x-csrf-token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    user: User
    session: AuthSession


def current_principal(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    found = service.lookup_session(db, settings, token) if token else None
    if found is None:
        raise Unauthenticated("Please sign in.")
    user, session = found
    if request.method not in _SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not constant_time_equal(
            hash_token(supplied, settings.secret_key), session.csrf_hash
        ):
            raise Forbidden("Missing or invalid CSRF token.", code="csrf_failed")
    limiter.check(f"user:{user.id}", settings.rate_limit_per_minute)
    return Principal(user=user, session=session)


def current_user(principal: Principal = Depends(current_principal)) -> User:
    return principal.user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise Forbidden("Administrator access is required.", code="admin_required")
    return user
