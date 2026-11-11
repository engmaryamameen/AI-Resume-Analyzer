"""Mailbox ownership and recovery. Transactions lock the user before touching tokens/sessions.

Only token hashes reach the database; raw links live only in the delivery task's memory.
"""

import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ServiceUnavailable, ValidationFailed
from app.core.logging import get_logger
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    normalise_email,
    password_policy_violation,
)
from app.db.models import AccountToken, AuditEvent, User
from app.db.models import Session as AuthSession
from app.db.session import session_scope

Purpose = Literal["verify_email", "reset_password"]
log = get_logger(__name__)


def require_delivery(settings: Settings) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise ServiceUnavailable(
            "Account email delivery is unavailable. Please try again later.",
            code="email_unavailable",
        )
    if settings.is_production and not settings.public_app_url.startswith("https://"):
        raise ServiceUnavailable("Account email delivery is unavailable.", code="email_unavailable")


def issue_token(db: Session, settings: Settings, user: User, purpose: Purpose) -> str:
    # Serialize issuance with consumption; an older email cannot remain usable after reissue.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    db.execute(
        delete(AccountToken).where(AccountToken.user_id == user.id, AccountToken.purpose == purpose)
    )
    token = new_token()
    db.add(
        AccountToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token, settings.secret_key),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    db.add(AuditEvent(user_id=user.id, action=f"account.{purpose}.requested"))
    db.flush()
    return token


def deliver(settings: Settings, email: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.smtp_from, email, subject
    message.set_content(text)
    with smtplib.SMTP_SSL(
        settings.smtp_host, settings.smtp_port, timeout=10, context=ssl.create_default_context()
    ) as smtp:
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_account_link(settings: Settings, email: str, purpose: Purpose) -> None:
    """Runs after an accepted HTTP response; rechecks the current account state.

    Delivery failure never logs an address, token or SMTP exception text. Request a new link to retry.
    """
    try:
        try:
            address = normalise_email(email)
        except ValueError:
            return
        with session_scope() as db:
            user = db.scalar(select(User).where(User.email == address).with_for_update())
            if user is None or (purpose == "verify_email" and user.email_verified_at is not None):
                return
            token = issue_token(db, settings, user, purpose)
        route = "verify-email" if purpose == "verify_email" else "reset-password"
        # Fragment tokens avoid access logs and Referer. User must explicitly submit the form.
        link = f"{settings.public_app_url.rstrip('/')}/{route}#token={token}"
        deliver(
            settings,
            address,
            "Verify your email" if purpose == "verify_email" else "Reset your password",
            f"Open this link within 30 minutes:\n{link}\n\nIf you did not request this, ignore this message.",
        )
    except Exception as exc:  # trusted background-task boundary: never expose mailbox or token
        log.error("account_email_failed", extra={"error_type": type(exc).__name__})


def consume_token(
    db: Session, settings: Settings, token: str, purpose: Purpose, password: str | None = None
) -> User:
    # Mailbox ownership establishes the credential, including when somebody else
    # pre-registered this email. Never activate an attacker-chosen password.
    problem = password_policy_violation(password or "")
    if problem:
        raise ValidationFailed(problem, code="weak_password")
    token_hash = hash_token(token, settings.secret_key)
    owner = db.scalar(
        select(AccountToken.user_id).where(
            AccountToken.token_hash == token_hash, AccountToken.purpose == purpose
        )
    )
    user = db.scalar(select(User).where(User.id == owner).with_for_update()) if owner else None
    record = (
        db.scalar(
            select(AccountToken)
            .where(
                AccountToken.token_hash == token_hash,
                AccountToken.purpose == purpose,
                AccountToken.expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        if user
        else None
    )
    if record is None or user is None:
        raise ValidationFailed(
            "This link is invalid or expired. Request a new one.", code="invalid_account_token"
        )
    user.email_verified_at = datetime.now(UTC)
    user.password_hash = hash_password(password or "")
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(AccountToken).where(AccountToken.user_id == user.id))
    db.add(AuditEvent(user_id=user.id, action=f"account.{purpose}.completed"))
    db.commit()
    return user


def notify_password_reset(settings: Settings, email: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        return
    try:
        deliver(
            settings,
            email,
            "Your password was changed",
            "Your password was changed and all sessions were signed out. If this was not you, recover your account immediately and secure your mailbox.",
        )
    except Exception as exc:
        log.error("account_notification_failed", extra={"error_type": type(exc).__name__})
