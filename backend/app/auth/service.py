from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, Unauthenticated, ValidationFailed
from app.core.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_token,
    normalise_email,
    password_policy_violation,
    verify_password,
)
from app.db.models import AuditEvent, Session as AuthSession, User


def register(db: Session, email: str, password: str, request_id: str | None) -> User:
    """Every account starts as a normal user. Administrators are granted out of band (app.cli)."""
    try:
        normalised = normalise_email(email)
    except ValueError as exc:
        raise ValidationFailed("Enter a valid email address.", code="invalid_email") from exc
    problem = password_policy_violation(password)
    if problem:
        raise ValidationFailed(problem, code="weak_password")
    user = User(email=normalised, password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc
    db.add(AuditEvent(user_id=user.id, action="account.registered", target_type="user",
                      target_id=str(user.id), request_id=request_id))
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str, request_id: str | None) -> User:
    try:
        normalised = normalise_email(email)
    except ValueError:
        normalised = ""
    user = db.execute(select(User).where(User.email == normalised)).scalar_one_or_none()
    ok = verify_password(password, user.password_hash if user else None)  # same work for unknown accounts
    if not ok or user is None:
        db.add(AuditEvent(user_id=user.id if user else None, action="login.failed", request_id=request_id))
        db.commit()
        raise Unauthenticated("Email or password is incorrect.", code="invalid_credentials")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def confirm_password(user: User, password: str) -> None:
    """Re-authentication for destructive actions."""
    if not verify_password(password, user.password_hash):
        # 403, not 401: the session is fine, so the client must not treat this as being signed out.
        raise Forbidden("That password isn't correct.", code="password_incorrect")


def create_session(db: Session, settings: Settings, user: User) -> tuple[str, str]:
    """Returns (session_token, csrf_token). Only keyed hashes are stored."""
    token, csrf = new_token(), new_token()
    now = datetime.now(UTC)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < now))
    db.add(AuthSession(
        user_id=user.id, token_hash=hash_token(token, settings.secret_key),
        csrf_hash=hash_token(csrf, settings.secret_key),
        expires_at=now + timedelta(hours=settings.session_ttl_hours)))
    db.add(AuditEvent(user_id=user.id, action="login.succeeded"))
    db.commit()
    return token, csrf


def revoke_session(db: Session, settings: Settings, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token, settings.secret_key)))
        db.commit()


def lookup_session(db: Session, settings: Settings, token: str) -> tuple[User, AuthSession] | None:
    row = db.execute(
        select(User, AuthSession).join(AuthSession, AuthSession.user_id == User.id).where(
            AuthSession.token_hash == hash_token(token, settings.secret_key),
            AuthSession.expires_at > datetime.now(UTC))
    ).first()
    return (row[0], row[1]) if row else None
