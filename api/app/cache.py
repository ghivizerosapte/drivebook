"""In-process calendar cache with optional Redis later (same interface)."""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any, Optional

_lock = Lock()
_store: dict[str, tuple[float, str]] = {}


def get_json(key: str) -> Optional[Any]:
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        exp, raw = item
        if exp < time.time():
            _store.pop(key, None)
            return None
        return json.loads(raw)


def set_json(key: str, value: Any, ttl_sec: int = 60) -> None:
    with _lock:
        _store[key] = (time.time() + ttl_sec, json.dumps(value, default=str))


def invalidate_prefix(prefix: str) -> int:
    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            _store.pop(k, None)
        return len(keys)
