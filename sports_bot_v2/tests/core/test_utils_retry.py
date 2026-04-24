"""Tests for core.utils.retry_with_backoff — 429 Retry-After honoring."""
from __future__ import annotations

import time
from email.message import Message
from urllib.error import HTTPError

import pytest

from core.utils import retry_with_backoff


def _make_429(retry_after: str | None) -> HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return HTTPError(url="http://x", code=429, msg="Too Many Requests", hdrs=hdrs, fp=None)


def test_honors_retry_after_seconds(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429("2")
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)

    assert result == "ok"
    assert calls["n"] == 2
    # First sleep must be >= 2s (server's hint), not the 0.5s default first backoff
    assert slept and slept[0] >= 2.0


def test_falls_back_to_exponential_when_no_retry_after(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429(None)
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)

    assert result == "ok"
    # Without Retry-After we fall back to ~0.5s base backoff
    assert slept and slept[0] < 2.0


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def fn():
        raise _make_429("1")

    with pytest.raises(HTTPError):
        retry_with_backoff(fn, retries=2, backoff_ms=100)


def test_clamps_very_large_retry_after(monkeypatch):
    """A server asking us to wait longer than MAX_RETRY_AFTER_S is clamped."""
    from core import utils as u

    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(u, "MAX_RETRY_AFTER_S", 10.0)

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429("86400")  # 24h — must be clamped
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)

    assert result == "ok"
    assert slept and slept[0] == 10.0


def test_retry_after_zero_falls_back_to_exponential(monkeypatch):
    """Retry-After: 0 should NOT cause time.sleep(0) — fall back to exponential."""
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429("0")
        return "ok"

    retry_with_backoff(fn, retries=3, backoff_ms=500)
    # Should have used exponential fallback, not 0
    assert slept and slept[0] > 0.0
    assert slept[0] < 2.0  # well below 2s; exponential at attempt 0 is ~0.5s + jitter


def test_honors_retry_after_http_date(monkeypatch):
    """HTTP-date form (RFC 9110) should be parsed to seconds-until."""
    from datetime import datetime, timezone, timedelta
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    # Build an HTTP-date ~5s in the future
    future = datetime.now(timezone.utc) + timedelta(seconds=5)
    # RFC 7231 IMF-fixdate format (single-space separators, GMT)
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _make_429(http_date)
        return "ok"

    retry_with_backoff(fn, retries=3, backoff_ms=500)
    # Should have slept approximately 5s (allow wide window for CI clock drift)
    assert slept and 3.0 <= slept[0] <= 6.0


def test_non_http_transient_still_exponential(monkeypatch):
    """URLError (non-HTTPError) must never hit _retry_after_seconds path."""
    import urllib.error
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise urllib.error.URLError("connection reset")
        return "ok"

    result = retry_with_backoff(fn, retries=3, backoff_ms=500)
    assert result == "ok"
    # Should have used exponential backoff, not a hint (hint path should never fire for URLError)
    assert slept and slept[0] < 2.0


def test_gives_up_after_correct_attempt_count(monkeypatch):
    """retries=2 means fn is called 3 times total (initial + 2 retries)."""
    monkeypatch.setattr(time, "sleep", lambda s: None)

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _make_429("1")

    with pytest.raises(HTTPError):
        retry_with_backoff(fn, retries=2, backoff_ms=100)

    assert calls["n"] == 3  # 1 initial + 2 retries
