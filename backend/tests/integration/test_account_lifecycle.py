"""Account recovery, ownership, atomic registration and session revocation on PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth import lifecycle, service
from app.core.config import get_settings
from app.core.errors import Unauthenticated, ValidationFailed
from app.db.models import AccountToken, User
from app.db.models import Session as AuthSession
from app.db.session import session_scope

pytestmark = pytest.mark.integration


def test_recovery_consumes_token_once_and_revokes_all_sessions(make_user):
    _, client = make_user()
    settings = get_settings()
    with session_scope() as db:
        user = db.scalar(select(User))
        token = lifecycle.issue_token(db, settings, user, "reset_password")
        verification = lifecycle.issue_token(db, settings, user, "verify_email")
        assert db.scalar(select(AccountToken)).token_hash != token
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "another secure password phrase"},
    )
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "another secure password phrase"},
        ).status_code
        == 422
    )
    invalidated = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification, "password": "mailbox owner password phrase"},
    )
    assert invalidated.status_code == 422
    assert invalidated.json()["error"]["code"] == "invalid_account_token"
    with session_scope() as db:
        assert db.scalar(select(AuthSession)) is None
        assert db.scalar(select(AccountToken)) is None
        assert db.scalar(select(User)).email_verified_at is not None
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "another secure password phrase"},
        ).status_code
        == 200
    )


def test_expiry_reissue_and_purpose_binding(make_user):
    make_user()
    settings = get_settings()
    with session_scope() as db:
        user = db.scalar(select(User))
        first = lifecycle.issue_token(db, settings, user, "verify_email")
        second = lifecycle.issue_token(db, settings, user, "verify_email")
    with session_scope() as db:
        with pytest.raises(ValidationFailed):
            lifecycle.consume_token(
                db, settings, first, "verify_email", "mailbox owner password phrase"
            )
    with session_scope() as db:
        with pytest.raises(ValidationFailed):
            lifecycle.consume_token(
                db, settings, second, "reset_password", "another secure password phrase"
            )
    with session_scope() as db:
        record = db.scalar(select(AccountToken))
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with session_scope() as db:
        with pytest.raises(ValidationFailed):
            lifecycle.consume_token(
                db, settings, second, "verify_email", "mailbox owner password phrase"
            )


def test_registration_rolls_back_if_session_cannot_be_issued(db_engine):
    with pytest.raises(RuntimeError), session_scope() as db:
        service.register(db, "atomic@example.test", "correct horse battery staple", None)
        raise RuntimeError("session issuance failed")
    with session_scope() as db:
        assert db.scalar(select(User).where(User.email == "atomic@example.test")) is None


def test_recovery_distinguishes_missing_account_without_sending_mail(make_user, monkeypatch):
    _, client = make_user()
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "mail.example.test")
    monkeypatch.setattr(settings, "smtp_from", "accounts@example.test")
    messages = []
    monkeypatch.setattr(lifecycle, "deliver", lambda *args: messages.append(args))
    known = client.post("/api/v1/auth/forgot-password", json={"email": " USER@EXAMPLE.COM "})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == 204
    assert known.content == b""
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "account_not_found"
    assert len(messages) == 1
    assert "#token=" in messages[0][-1]


def test_unverified_user_cannot_use_workspace_in_production(make_user, monkeypatch):
    _, client = make_user()
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/api/v1/resumes").json()["error"]["code"] == "email_unverified"


def test_session_revocation_is_scoped_to_owner(make_user):
    _, first = make_user()
    _, second = make_user("other@example.test")
    own = first.get("/api/v1/auth/sessions").json()[0]
    other = second.get("/api/v1/auth/sessions").json()[0]
    assert first.delete("/api/v1/auth/sessions/" + other["id"]).status_code == 204
    assert second.get("/api/v1/auth/me").status_code == 200
    assert first.delete("/api/v1/auth/sessions/" + own["id"]).status_code == 204
    assert first.get("/api/v1/auth/me").status_code == 401


def test_public_registration_does_not_expose_existing_account_or_issue_a_session(
    db_engine, client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "public_app_url", "https://app.example.test")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "accounts@example.test")
    monkeypatch.setattr(lifecycle, "deliver", lambda *_: None)
    payload = {"email": "private@example.test", "password": "correct horse battery staple"}
    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json().keys() == second.json().keys()
    assert first.json() == second.json() == {"user": None, "email_verification_required": True}
    assert not first.cookies and not second.cookies
    with session_scope() as db:
        assert len(db.scalars(select(User)).all()) == 1
        assert db.scalar(select(AuthSession)) is None


def test_concurrent_token_consumption_succeeds_once(make_user):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    make_user()
    settings = get_settings()
    with session_scope() as db:
        token = lifecycle.issue_token(db, settings, db.scalar(select(User)), "verify_email")
    start = Barrier(2)

    def consume():
        start.wait(timeout=5)
        try:
            with session_scope() as db:
                lifecycle.consume_token(
                    db, settings, token, "verify_email", "mailbox owner password phrase"
                )
            return True
        except ValidationFailed:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: consume(), range(2))) == [False, True]


def test_verification_replaces_pre_registered_password_and_revokes_attacker_sessions(make_user):
    _, client = make_user(password="attacker chosen password phrase")
    settings = get_settings()
    with session_scope() as db:
        token = lifecycle.issue_token(db, settings, db.scalar(select(User)), "verify_email")
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": token, "password": "mailbox owner password phrase"},
    )
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "attacker chosen password phrase"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "mailbox owner password phrase"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize("purpose", ["reset_password", "verify_email"])
def test_credential_verification_and_session_issue_are_one_locked_unit(make_user, purpose):
    """A real competing connection cannot reset a credential between these two operations."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    from app.db.session import get_engine

    make_user()
    settings = get_settings()
    with session_scope() as db:
        owner = db.scalar(select(User))
        token = lifecycle.issue_token(db, settings, owner, purpose)
    with Session(get_engine()) as login, Session(get_engine()) as reset:
        user = service.authenticate(login, "user@example.com", "correct horse battery staple", None)
        reset.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(OperationalError):
            lifecycle.consume_token(reset, settings, token, purpose, "a new secure password phrase")
        reset.rollback()
        session_token, _ = service.create_session(login, settings, user)
        lifecycle.consume_token(reset, settings, token, purpose, "a new secure password phrase")
    with session_scope() as db:
        assert service.lookup_session(db, settings, session_token) is None
        with pytest.raises(Unauthenticated) as rejected:
            service.authenticate(db, "user@example.com", "correct horse battery staple", None)
        assert getattr(rejected.value, "code", None) == "invalid_credentials"
        assert service.authenticate(db, "user@example.com", "a new secure password phrase", None)


def test_account_deletion_rechecks_a_principal_loaded_before_reset(make_user, tmp_path):
    """Model an in-flight request: authentication ran before the competing reset committed."""
    from app.api.auth_router import delete_account
    from app.api.schemas import DeleteAccountIn
    from app.auth.deps import Principal
    from app.documents.storage import LocalPrivateStore

    _, client = make_user()
    settings = get_settings()
    with session_scope() as db:
        user, session = service.lookup_session(db, settings, client.cookies.get("rs_session"))
        principal = Principal(user=user, session=session)
        token = lifecycle.issue_token(db, settings, user, "reset_password")
    with session_scope() as db:
        lifecycle.consume_token(db, settings, token, "reset_password", "new secure password phrase")
    with session_scope() as db:
        with pytest.raises(Unauthenticated):
            delete_account(
                DeleteAccountIn(password="correct horse battery staple"),
                principal,
                db,
                LocalPrivateStore(tmp_path / "files"),
            )
    with session_scope() as db:
        assert db.scalar(select(User).where(User.id == principal.user.id)) is not None


@pytest.mark.parametrize(
    "purpose,route", [("reset_password", "reset-password"), ("verify_email", "verify-email")]
)
def test_account_links_accept_eight_characters_and_preserve_token_after_short_password(
    make_user, purpose, route
):
    _, client = make_user()
    settings = get_settings()
    with session_scope() as db:
        user = db.scalar(select(User))
        token = lifecycle.issue_token(db, settings, user, purpose)
    short = client.post(f"/api/v1/auth/{route}", json={"token": token, "password": "Lime#42"})
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "weak_password"
    accepted = client.post(f"/api/v1/auth/{route}", json={"token": token, "password": "Lime#427"})
    assert accepted.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": "Lime#427"}
        ).status_code
        == 200
    )


def test_registration_password_minimum_is_eight_characters(client):
    short = client.post(
        "/api/v1/auth/register", json={"email": "boundary@example.test", "password": "Lime#42"}
    )
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "weak_password"
    accepted = client.post(
        "/api/v1/auth/register", json={"email": "boundary@example.test", "password": "Lime#427"}
    )
    assert accepted.status_code == 201


def test_recovery_rejects_malformed_email(client):
    response = client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_email"


def test_missing_recovery_accounts_remain_rate_limited(client, db_engine):
    for _ in range(3):
        response = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
        assert response.json()["error"]["code"] == "account_not_found"
    response = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    assert response.status_code == 429
