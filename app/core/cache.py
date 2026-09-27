"""Tiny cache with Redis-if-available, else in-memory TTL fallback.

Used for read-heavy, rarely-changing data (centre listings).
Never fails the request: any Redis error degrades to in-memory/no-cache.
"""

import json
import time
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("eve.cache")

_memory: dict[str, tuple[float, str]] = {}
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.REDIS_URL:
        return None
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        log.info("cache_backend", backend="redis")
        return client
    except Exception as exc:  # pragma: no cover - depends on infra
        log.warning("redis_unavailable_fallback_memory", error=str(exc))
        return None


def cache_get(key: str) -> Optional[Any]:
    # Try Redis first
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    # In-memory fallback
    item = _memory.get(key)
    if not item:
        return None
    expires_at, raw = item
    if time.time() > expires_at:
        _memory.pop(key, None)
        return None
    return json.loads(raw)


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    raw = json.dumps(value, default=str)
    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, raw)
            return
        except Exception:
            pass
    _memory[key] = (time.time() + ttl_seconds, raw)


def cache_invalidate_prefix(prefix: str) -> None:
    client = _get_redis()
    if client is not None:
        try:
            for key in client.scan_iter(f"{prefix}*"):
                client.delete(key)
        except Exception:
            pass
    for key in [k for k in _memory if k.startswith(prefix)]:
        _memory.pop(key, None)
