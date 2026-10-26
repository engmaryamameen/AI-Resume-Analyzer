import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.metrics import DB_QUERY_SECONDS


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    engine = create_engine(
        s.database_url,
        pool_size=10,
        max_overflow=5,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"options": "-c statement_timeout=15000 -c idle_in_transaction_session_timeout=30000"},
    )

    @event.listens_for(engine, "before_cursor_execute")
    def _start(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        conn.info["q_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _stop(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        started = conn.info.pop("q_start", None)
        if started is not None:
            DB_QUERY_SECONDS.observe(time.perf_counter() - started)

    return engine


@lru_cache
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session (one transaction scope) per request, never shared."""
    db = _factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """For worker code: commit on success, roll back on any failure."""
    db = _factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
