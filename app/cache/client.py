"""Cache abstraction.

Production uses Redis (redis-py); the test suite injects fakeredis, and a tiny
in-process implementation backs environments where neither is installed. The API
layer only depends on the small protocol below.
"""

from __future__ import annotations

import contextlib
import json
import time
from typing import Any, Protocol

from app.config import get_settings


class CacheClient(Protocol):
    def get_json(self, key: str) -> dict[str, Any] | None: ...

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None: ...

    def delete(self, *keys: str) -> None: ...

    def close(self) -> None: ...


class InMemoryCache:
    """Process-local TTL map used when Redis is not configured."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get_json(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        data: dict[str, Any] = json.loads(payload)
        return data

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, json.dumps(value, default=str))

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def close(self) -> None:
        self._store.clear()


class RedisCache:
    """Thin adapter over redis-py exposing only what the dashboard needs."""

    def __init__(self, url: str) -> None:
        import redis

        self._client: Any = redis.Redis.from_url(url, decode_responses=True)

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        data: dict[str, Any] = json.loads(raw)
        return data

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._client.set(key, json.dumps(value, default=str), ex=ttl_seconds)

    def delete(self, *keys: str) -> None:
        if keys:
            self._client.delete(*keys)

    def close(self) -> None:
        self._client.close()


class FallbackCache:
    """Serve from Redis when it answers, otherwise degrade to an in-process map.

    A dashboard panel must not fail because the cache node is down; the response is
    still correct, it is simply recomputed on every request.
    """

    def __init__(self, primary: CacheClient, secondary: CacheClient) -> None:
        self._primary = primary
        self._secondary = secondary

    def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            return self._primary.get_json(key)
        except Exception:
            # Cache failures must never break the API.
            return self._secondary.get_json(key)

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            self._primary.set_json(key, value, ttl_seconds)
        except Exception:
            self._secondary.set_json(key, value, ttl_seconds)

    def delete(self, *keys: str) -> None:
        try:
            self._primary.delete(*keys)
        except Exception:
            self._secondary.delete(*keys)

    def close(self) -> None:
        for client in (self._primary, self._secondary):
            with contextlib.suppress(Exception):
                client.close()


def build_cache(url: str | None = None) -> CacheClient:
    """Redis in production, in-process fallback when Redis is unreachable."""
    settings = get_settings()
    target = url if url is not None else settings.redis_url
    if not target:
        return InMemoryCache()
    try:
        redis_cache: CacheClient = RedisCache(target)
    except Exception:  # pragma: no cover - only on a broken driver install
        return InMemoryCache()
    return FallbackCache(redis_cache, InMemoryCache())
