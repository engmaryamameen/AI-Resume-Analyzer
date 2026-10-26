from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.logging import request_id_var
from app.documents.storage import LocalPrivateStore


@lru_cache
def _store_for(path: Path) -> LocalPrivateStore:
    return LocalPrivateStore(path)


def get_store(settings: Settings = Depends(get_settings)) -> LocalPrivateStore:
    return _store_for(settings.storage_dir)


def current_request_id() -> str | None:
    return request_id_var.get()
