"""Bounded, process-local sliding-window rate limiter.

Limits are per API process; multi-instance deployments need an upstream shared limiter.
At capacity, new keys fail closed until an existing key expires.
"""

import threading
import time
from collections import deque

from app.core.errors import RateLimited


class RateLimiter:
    def __init__(self, max_keys: int = 50_000) -> None:
        if max_keys < 1:
            raise ValueError("max_keys must be positive")
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._expires: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= self._max_keys:
                    self._evict(now)
                if len(self._hits) >= self._max_keys:
                    raise RateLimited("Too many requests. Please wait a moment and retry.")
                hits = deque()
                self._hits[key] = hits
            if self._expires.get(key, 0) <= now:
                hits.clear()
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimited("Too many requests. Please wait a moment and retry.")
            hits.append(now)
            self._expires[key] = now + window_seconds

    def _evict(self, now: float) -> None:
        for key, expiry in list(self._expires.items()):
            if expiry <= now:
                del self._hits[key]
                del self._expires[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._expires.clear()


limiter = RateLimiter()
