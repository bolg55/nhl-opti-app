from datetime import datetime, timezone
from typing import Any

_cache: dict[str, dict] = {}


def get_cached(key: str, ttl_seconds: int) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    age = (datetime.now(timezone.utc) - entry["fetched_at"]).total_seconds()
    if age >= ttl_seconds:
        return None
    return entry["data"]


def set_cached(key: str, data: Any) -> None:
    _cache[key] = {"data": data, "fetched_at": datetime.now(timezone.utc)}


def clear_cache(key: str | None = None) -> None:
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)
