"""
core/utils.py — shared helpers for sports_bot_v2
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable


# Maximum honored Retry-After hint in seconds. A server asking us to wait
# longer than this is treated as misconfigured; we clamp and try again sooner.
MAX_RETRY_AFTER_S = float(os.getenv("MAX_RETRY_AFTER_S", "120"))


def atomic_write_json(path: str, data: Any) -> None:
    """Write JSON atomically: write to .tmp then os.replace() to destination.
    Retries rename on PermissionError (Windows file-lock race with readers)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.05 * (attempt + 1))
                else:
                    raise
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def config_hash(env_vars: list[str]) -> str:
    """Short hash of key env var values — detects config drift between runs."""
    parts = []
    for k in sorted(env_vars):
        v = os.getenv(k, "")
        parts.append(f"{k}={v}")
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def http_get_json(url: str, timeout: int = 15, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "march-madness-bot/1.0", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 425, 429, 500, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError))


def _retry_after_seconds(exc: Exception) -> float | None:
    """If exc is an HTTPError carrying a Retry-After header, return seconds to wait.

    Accepts both numeric delta-seconds and HTTP-date forms per RFC 9110 §10.2.3.
    Returns None if header is missing or unparseable.
    """
    if not isinstance(exc, urllib.error.HTTPError):
        return None
    try:
        raw = exc.headers.get("Retry-After") if exc.headers else None
    except AttributeError:
        raw = None
    if not raw:
        return None
    text = str(raw).strip()
    # Numeric delta-seconds form
    try:
        return float(text)
    except (TypeError, ValueError):
        pass
    # HTTP-date form
    try:
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        dt = parsedate_to_datetime(text)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return delta if delta > 0 else 0.0
    except (TypeError, ValueError):
        return None


def retry_with_backoff(fn: Callable, retries: int = 3, backoff_ms: int = 500) -> Any:
    """Exponential backoff + jitter on transient errors.

    If the server returns HTTP 429 with a numeric `Retry-After` header, sleep for
    that many seconds instead of the computed backoff.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= retries or not is_transient_error(exc):
                raise
            hinted = _retry_after_seconds(exc)
            if hinted is not None and hinted > 0:
                sleep_s = min(hinted, MAX_RETRY_AFTER_S)
            else:
                sleep_ms = backoff_ms * (2 ** attempt) + random.randint(0, max(50, backoff_ms // 3))
                sleep_s = sleep_ms / 1000.0
            time.sleep(sleep_s)
            attempt += 1


def parse_utc_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        s = s.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_ts() -> float:
    return time.time()


def load_env(path: str = ".env") -> None:
    """Minimal dotenv loader — sets os.environ for keys not already set."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        pass


def append_jsonl(path: str, record: Any) -> None:
    """Append one JSON line to a JSONL file (creates file if needed)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
