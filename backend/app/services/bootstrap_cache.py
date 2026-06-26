from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

_lock = Lock()
_cache: dict[int, _Entry] = {}


@dataclass
class _Entry:
    payload: dict[str, Any]
    expires_at: float


def get(user_id: int) -> dict[str, Any] | None:
    now = time.monotonic()
    with _lock:
        entry = _cache.get(user_id)
        if entry is None:
            return None
        if entry.expires_at <= now:
            del _cache[user_id]
            return None
        return entry.payload


def set(user_id: int, payload: dict[str, Any], ttl_seconds: float) -> None:
    with _lock:
        _cache[user_id] = _Entry(payload, time.monotonic() + ttl_seconds)


def invalidate(user_id: int | None = None) -> None:
    with _lock:
        if user_id is None:
            _cache.clear()
        else:
            _cache.pop(user_id, None)
