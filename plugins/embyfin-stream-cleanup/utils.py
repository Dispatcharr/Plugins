"""Shared utility functions used across all modules."""

import ipaddress
import logging

logger = logging.getLogger(__name__)

_STALE_SERVER_PREFIXES = (
    "media_server_url_",
    "media_server_api_key_",
    "media_server_identifier_",
)


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


def normalize_channel_number(ch_num) -> str:
    """Normalise a raw channel number value to a consistent string.

    Converts whole-number floats to ints (e.g. ``"5.0"`` → ``"5"``),
    leaving fractional values and strings that aren't numbers untouched.
    Returns an empty string if *ch_num* is falsy.
    """
    if not ch_num:
        return ""
    ch_num = str(ch_num).strip()
    try:
        num = float(ch_num)
        return str(int(num)) if num == int(num) else ch_num
    except (ValueError, TypeError):
        return ch_num


def is_hostname(ident: str) -> bool:
    """Return True if *ident* is a hostname that needs DNS resolution.

    Returns False for CIDR blocks and plain IP addresses, which don't
    require resolution.
    """
    if "/" in ident:
        return False
    try:
        ipaddress.ip_address(ident)
        return False
    except ValueError:
        return True


def prune_stale_server_keys(settings: dict, count: int) -> bool:
    """Remove suffixed media-server keys whose index exceeds *count*.

    Operates in-place on *settings*.  Returns True if any keys were removed.
    Server 1 uses bare keys (no suffix), so only ``_N`` suffixed keys for
    N > count are touched.
    """
    changed = False
    for k in [k for k in settings if k.startswith(_STALE_SERVER_PREFIXES)]:
        suffix = k.rsplit("_", 1)[-1]
        try:
            if int(suffix) > count:
                del settings[k]
                logger.debug(f"Pruned stale server setting: {k}")
                changed = True
        except (ValueError, TypeError):
            pass
    return changed
