"""Capacity, expiration, and contention contracts for the process-local limiter."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.errors import RateLimited
from app.core.ratelimit import RateLimiter


def test_capacity_rejects_new_keys_without_eviction_of_active_keys(monkeypatch):
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: 0.0)
    limiter = RateLimiter(max_keys=2)
    limiter.check('one', 2)
    limiter.check('two', 2)
    with pytest.raises(RateLimited):
        limiter.check('three', 2)
    limiter.check('one', 2)
    assert len(limiter._hits) == 2
    with pytest.raises(RateLimited):
        limiter.check('one', 2)


def test_expiration_allows_new_clients(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: clock[0])
    limiter = RateLimiter(max_keys=1)
    limiter.check('old', 1, 10)
    clock[0] = 10.0
    limiter.check('new', 1, 10)
    assert list(limiter._hits) == ['new']


def test_concurrent_limit_is_atomic():
    limiter = RateLimiter(max_keys=1)
    def attempt(_):
        try:
            limiter.check('shared', 3)
            return True
        except RateLimited:
            return False
    with ThreadPoolExecutor(max_workers=24) as pool:
        assert sum(pool.map(attempt, range(24))) == 3
    assert len(limiter._hits['shared']) == 3


def test_short_window_does_not_evict_long_window(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: clock[0])
    limiter = RateLimiter(max_keys=2)
    limiter.check('long', 1, 3600)
    limiter.check('short', 1, 5)
    clock[0] = 6.0
    limiter.check('replacement', 1, 5)
    assert set(limiter._hits) == {'long', 'replacement'}
    with pytest.raises(RateLimited):
        limiter.check('long', 1, 3600)


def test_long_window_does_not_keep_short_window_at_capacity(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: clock[0])
    limiter = RateLimiter(max_keys=2)
    limiter.check('short', 1, 5)
    limiter.check('long', 1, 3600)
    clock[0] = 6.0
    limiter.check('replacement', 1, 3600)
    assert set(limiter._hits) == {'long', 'replacement'}


def test_expiration_tracks_last_accepted_request(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: clock[0])
    limiter = RateLimiter(max_keys=1)
    limiter.check('a', 2, 10)
    clock[0] = 7.0
    limiter.check('a', 2, 10)
    clock[0] = 11.0
    with pytest.raises(RateLimited):
        limiter.check('b', 1, 10)
    clock[0] = 17.0
    limiter.check('b', 1, 10)
    assert list(limiter._hits) == ['b']


def test_expired_key_can_be_reused_with_a_longer_window(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.core.ratelimit.time.monotonic', lambda: clock[0])
    limiter = RateLimiter(max_keys=1)
    limiter.check('shared', 1, 2)
    clock[0] = 3.0
    limiter.check('shared', 1, 3600)
    assert len(limiter._hits['shared']) == 1
