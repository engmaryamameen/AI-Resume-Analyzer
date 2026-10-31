"""In-process sliding-window rate limiter.

Limitation (documented in docs/deployment.md): state is per process, so with N API replicas the
effective limit is N x the configured value. Put a gateway limiter in front for production.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise RateLimited("Too many requests. Please wait a moment and retry.")
            q.append(now)
            if len(self._hits) > 50_000:
                self._evict(now, window_seconds)

    def _evict(self, now: float, window: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] > window]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
