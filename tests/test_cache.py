from datetime import datetime, timedelta, timezone
from server.cache import get_cached, set_cached, clear_cache, _cache


def test_set_and_get_within_ttl():
    clear_cache()
    set_cached("test_key", {"foo": "bar"})
    result = get_cached("test_key", ttl_seconds=60)
    assert result == {"foo": "bar"}


def test_get_returns_none_when_expired():
    clear_cache()
    set_cached("test_key", {"foo": "bar"})
    # Manually backdate the cache entry
    _cache["test_key"]["fetched_at"] = datetime.now(timezone.utc) - timedelta(seconds=120)
    result = get_cached("test_key", ttl_seconds=60)
    assert result is None


def test_get_returns_none_for_missing_key():
    clear_cache()
    result = get_cached("nonexistent", ttl_seconds=60)
    assert result is None


def test_clear_specific_key():
    clear_cache()
    set_cached("a", 1)
    set_cached("b", 2)
    clear_cache("a")
    assert get_cached("a", ttl_seconds=60) is None
    assert get_cached("b", ttl_seconds=60) == 2


def test_clear_all():
    clear_cache()
    set_cached("a", 1)
    set_cached("b", 2)
    clear_cache()
    assert get_cached("a", ttl_seconds=60) is None
    assert get_cached("b", ttl_seconds=60) is None
