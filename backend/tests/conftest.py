import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Settings must be in place before the app module is imported anywhere.
_TMP = tempfile.mkdtemp(prefix="resume-intel-test-")
os.environ.update({
    "APP_ENV": "test",
    "SECRET_KEY": "test-secret-key-that-is-long-enough-0123456789",
    "STORAGE_DIR": str(Path(_TMP) / "storage"),
    "MODEL_DIR": str(Path(_TMP) / "models"),  # empty: tests run the rule-based reading
    "ML_ENABLED": "false",
    "CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    "RATE_LIMIT_DEMO_PER_MINUTE": "1000",
})
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.core.ratelimit import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    limiter.reset()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c


def _requires_db() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL (disposable PostgreSQL) is not set")


@pytest.fixture
def db_engine():
    """A fresh schema on a DISPOSABLE database. Never point TEST_DATABASE_URL at real data."""
    _requires_db()
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.db.session import get_engine

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")
    yield engine


@pytest.fixture
def db(db_engine):
    from app.db.session import session_scope

    with session_scope() as session:
        yield session


@pytest.fixture
def make_user(client, db_engine):
    """Registers a user through the real API and returns (email, TestClient with its CSRF header set)."""
    from fastapi.testclient import TestClient

    from app.api.main import app

    created: list[TestClient] = []

    def _make(email: str = "user@example.com", password: str = "correct horse battery staple"):
        c = TestClient(app, base_url="http://localhost:8000")
        created.append(c)
        r = c.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert r.status_code == 201, r.text
        c.headers["X-CSRF-Token"] = c.cookies.get("rs_csrf")
        return email, c

    yield _make
    for c in created:
        c.close()


@pytest.fixture
def run_jobs():
    """Drains the queue synchronously with the rule-based engine, as the worker process would."""
    from app.jobs.worker import run_until_idle
    from app.ml.rules import RulesEngine

    def _run() -> None:
        run_until_idle(RulesEngine())

    return _run
