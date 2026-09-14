"""Shared utility functions used across all modules."""

import logging
import re

logger = logging.getLogger(__name__)


def escape_label(value) -> str:
    """Escape a string for use as a Prometheus label value.

    Order is critical: escape backslashes first, then double-quotes, then newlines.
    """
    if not value:
        return ""
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


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


def get_dispatcharr_version():
    """Return ``(version, timestamp, full_version)`` for the running Dispatcharr instance."""
    import sys

    dispatcharr_version = "unknown"
    dispatcharr_timestamp = None

    try:
        if '/app' not in sys.path:
            sys.path.insert(0, '/app')
        import version  # Dispatcharr's version module
        dispatcharr_version = getattr(version, '__version__', 'unknown')
        dispatcharr_timestamp = getattr(version, '__timestamp__', None)
    except Exception:
        try:
            with open('/app/version.py', 'r') as f:
                content = f.read()
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
            if m:
                dispatcharr_version = m.group(1)
            m = re.search(r"__timestamp__\s*=\s*['\"]([^'\"]+)['\"]", content)
            if m:
                dispatcharr_timestamp = m.group(1)
        except Exception:
            pass

    full_version = dispatcharr_version
    if dispatcharr_timestamp:
        full_version = f"v{dispatcharr_version}-{dispatcharr_timestamp}"

    return dispatcharr_version, dispatcharr_timestamp, full_version


def compare_versions(current: str, minimum: str) -> bool:
    """Return True if *current* >= *minimum* (semantic version comparison)."""
    try:
        current = current.lstrip('v')
        minimum = minimum.lstrip('v')
        c_parts = [int(x) for x in current.split('.')]
        m_parts = [int(x) for x in minimum.split('.')]
        while len(c_parts) < len(m_parts):
            c_parts.append(0)
        while len(m_parts) < len(c_parts):
            m_parts.append(0)
        for c, m in zip(c_parts, m_parts):
            if c > m:
                return True
            if c < m:
                return False
        return True
    except (ValueError, AttributeError):
        return True
