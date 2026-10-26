import os
import re
import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


class BlobStore(Protocol):
    def put(self, data: bytes) -> str: ...
    def path(self, key: str) -> Path: ...
    def delete(self, key: str) -> None: ...
    def stored(self) -> Iterator[tuple[str, float]]: ...


class LocalPrivateStore:
    """Files live under a private root with server-generated random keys.

    Nothing user-supplied reaches a path. Keys are validated on every access so a corrupted
    database row cannot be turned into a traversal.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def _resolve(self, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise ValueError("invalid storage key")
        p = (self.root / key[:2] / key).resolve()
        if self.root not in p.parents:
            raise ValueError("storage path escapes root")
        return p

    def put(self, data: bytes) -> str:
        key = secrets.token_hex(16)
        p = self._resolve(key)
        p.parent.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return key

    def path(self, key: str) -> Path:
        return self._resolve(key)

    def delete(self, key: str) -> None:
        try:
            self._resolve(key).unlink(missing_ok=True)
        except ValueError:
            return

    def stored(self) -> Iterator[tuple[str, float]]:
        """Every stored key with its modification time (used to find files no database row refers to)."""
        for path in self.root.glob("??/*"):
            if _KEY_RE.match(path.name) and path.is_file():
                yield path.name, path.stat().st_mtime
