"""Shared utility functions used across all modules."""

import logging

logger = logging.getLogger(__name__)


def normalize_host(host, default: str) -> str:
    """Return a clean host string, falling back to *default* if empty/None."""
    if host is None or not str(host).strip():
        return default
    return str(host).strip()


def redis_decode(value, default: str = '') -> str:
    """Decode a Redis bytes value to str, returning *default* if None."""
    if value is None:
        return default
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def get_redis_client():
    """Return the shared Dispatcharr Redis client, or None on failure."""
    try:
        from core.utils import RedisClient
        return RedisClient.get_client()
    except Exception:
        return None


def read_redis_flag(redis_client, key: str) -> bool:
    """Return True if the given Redis key holds the value '1'."""
    try:
        val = redis_client.get(key) if redis_client else None
        return val in (b"1", "1")
    except Exception:
        return False
