"""Hourly retention/guest cleanup; a supervised Compose service, with graceful shutdown."""

import signal
import threading

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.documents.storage import LocalPrivateStore
from app.maintenance import run_maintenance


def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    settings = get_settings()
    store = LocalPrivateStore(settings.storage_dir)
    while not stopped.is_set():
        try:
            with session_scope() as db:
                run_maintenance(db, store, settings)
        except Exception as exc:
            log.error("maintenance_failed", extra={"error_type": type(exc).__name__})
        stopped.wait(3600)


if __name__ == "__main__":
    main()
