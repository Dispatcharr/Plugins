"""Auto-start logic for the Emby Stream Cleanup monitor.

Uses Redis leader election (SET NX EX) so only one uWSGI worker starts the
monitor, even across multiple processes.

  1. Each worker calls ``attempt_autostart()`` from ``Plugin.__init__``.
  2. Background thread waits for Django ORM, reads plugin config.
  3. Races all workers with SET NX EX on a leader key.
  4. Winner clears stale state and starts the StreamMonitor (and optionally
     the debug server).

The per-process guard ``_autostart_launched`` prevents spawning duplicate
threads *within a single import cycle*, but ``force_reload=True`` in
Dispatcharr's plugin loader re-imports all modules, resetting module-level
state.  To handle that, the autostart thread also checks Redis for an
already-running monitor/server before doing anything destructive.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Per-process guard: only one autostart thread may be spawned per process.
_autostart_launched = False
_autostart_lock = threading.Lock()

_STARTUP_WAIT = 5   # seconds before the first config-read attempt
_RETRY_DELAY  = 3   # seconds between subsequent attempts
_MAX_ATTEMPTS = 8   # total attempts to read PluginConfig from the DB


def attempt_autostart(monitor) -> None:
    """Entry point from ``Plugin.__init__``.

    Spawns a daemon thread (at most once per OS process) that races via Redis
    NX to become the autostart leader and start the monitor.
    """
    global _autostart_launched
    with _autostart_lock:
        if _autostart_launched:
            logger.debug("Emby stream cleanup: auto-start already launched in this process, skipping")
            return
        _autostart_launched = True

    # Redis-level dedup is handled later inside the background thread
    # (leader election). We avoid touching Redis here because Plugin.__init__
    # runs at import time, potentially before Dispatcharr's Redis is ready.
    # Blocking here would stall the entire uWSGI worker boot.

    threading.Thread(
        target=_autostart_worker,
        args=(monitor,),
        daemon=True,
        name="emby-stream-autostart",
    ).start()


def cleanup_stale_state(redis_client) -> None:
    """Delete plugin Redis keys left over from a previous container lifecycle."""
    from .config import CLEANUP_REDIS_KEYS
    try:
        if redis_client:
            deleted = redis_client.delete(*CLEANUP_REDIS_KEYS)
            if deleted:
                logger.info(f"Startup cleanup: removed {deleted} stale plugin Redis key(s)")
            else:
                logger.debug("Startup cleanup: no stale Redis keys found")
    except Exception as e:
        logger.warning(f"Startup cleanup failed: {e}")


def _autostart_worker(monitor) -> None:
    """Background thread body."""
    from .config import (
        REDIS_KEY_LEADER, LEADER_TTL,
        DEFAULT_PORT, DEFAULT_HOST, PLUGIN_DB_KEY,
    )
    from .utils import get_redis_client, normalize_host

    # ── Step 0: Redis dedup (prevents redundant threads after force_reload) ──
    # This runs inside the thread (after the daemon is spawned) so it never
    # blocks uWSGI worker boot.  The initial sleep gives Redis time to be ready.
    time.sleep(_STARTUP_WAIT)
    try:
        from .config import REDIS_KEY_MONITOR
        _rc = get_redis_client()
        if _rc:
            _dedup_key = REDIS_KEY_LEADER + ":autostart_dedup"
            if not _rc.set(_dedup_key, "1", nx=True, ex=(_RETRY_DELAY * _MAX_ATTEMPTS) + 30):
                # Key exists, but if nothing is actually running or leading,
                # it's stale from a previous lifecycle.  Clear and proceed.
                if not _rc.get(REDIS_KEY_MONITOR) and not _rc.get(REDIS_KEY_LEADER):
                    logger.debug("Emby stream cleanup: stale autostart_dedup key, clearing")
                    _rc.delete(_dedup_key)
                    _rc.set(_dedup_key, "1", nx=True, ex=(_RETRY_DELAY * _MAX_ATTEMPTS) + 30)
                else:
                    logger.debug("Emby stream cleanup: auto-start already in progress (Redis dedup), skipping")
                    return
    except Exception:
        pass  # Redis not available yet, leader election will gate us

    # Try both key forms (underscore and hyphen)
    _plugin_keys = [PLUGIN_DB_KEY, PLUGIN_DB_KEY.replace('_', '-')]

    settings_dict: dict = {}

    for attempt in range(_MAX_ATTEMPTS):
        # First iteration has no sleep since _STARTUP_WAIT already elapsed above.
        if attempt > 0:
            time.sleep(_RETRY_DELAY)
        try:
            from apps.plugins.models import PluginConfig
            config = None
            for _key in _plugin_keys:
                config = PluginConfig.objects.filter(key=_key).first()
                if config is not None:
                    break
            if config is None:
                logger.debug(
                    f"Emby stream cleanup: PluginConfig not found yet "
                    f"(attempt {attempt + 1}/{_MAX_ATTEMPTS}, tried keys: {_plugin_keys})"
                )
                continue
            settings_dict = config.settings or {}
            if not config.enabled:
                logger.debug("Emby stream cleanup: plugin is disabled, skipping auto-start")
                return
            logger.debug(
                f"Emby stream cleanup: config read on attempt {attempt + 1}, plugin enabled"
            )
            break
        except Exception as e:
            logger.debug(
                f"Emby stream cleanup: auto-start attempt {attempt + 1} could not read config: {e}"
            )
    else:
        logger.warning(
            "Emby stream cleanup: could not read plugin config after all attempts, aborting auto-start"
        )
        return

    # Check that at least one media server has URL + API key + identifier
    has_configured_server = False
    ms_count = max(1, int(settings_dict.get("media_server_count", 1)))
    for n in range(1, ms_count + 1):
        sfx = f"_{n}" if n > 1 else ""
        url = (settings_dict.get(f"media_server_url{sfx}") or "").strip()
        key = (settings_dict.get(f"media_server_api_key{sfx}") or "").strip()
        ident = (settings_dict.get(f"media_server_identifier{sfx}") or "").strip()
        if url and key and ident:
            has_configured_server = True
            break
    if not has_configured_server:
        logger.warning(
            "Emby stream cleanup: auto-start skipped because no media server "
            "is fully configured (URL + API key + identifier)"
        )
        return

    # -- Respect manual stop ---------------------------------------------------
    # If the user manually stopped the monitor during this Dispatcharr runtime,
    # a Redis flag is set.  It's cleared on fresh boot (CLEANUP_REDIS_KEYS).
    try:
        from .config import REDIS_KEY_MANUAL_STOP
        _rc = get_redis_client()
        if _rc and _rc.get(REDIS_KEY_MANUAL_STOP):
            logger.debug("Emby stream cleanup: auto-start skipped (manually stopped)")
            return
    except Exception:
        pass

    # -- Leader election via Redis SET NX --------------------------------------
    redis_client = get_redis_client()
    if redis_client is None:
        logger.warning("Emby stream cleanup: cannot connect to Redis, aborting auto-start")
        return

    # Guard: if the monitor is already running (e.g. we were force-reloaded
    # and the old daemon thread is still alive), skip everything.  This
    # prevents cleanup_stale_state from nuking keys for a live server.
    from .config import REDIS_KEY_MONITOR as _RMON
    if redis_client.get(_RMON):
        logger.debug("Emby stream cleanup: monitor already running (Redis), skipping auto-start")
        return

    worker_id = f"{os.getpid()}-{threading.get_ident()}"
    won = redis_client.set(REDIS_KEY_LEADER, worker_id, nx=True, ex=LEADER_TTL)
    if not won:
        logger.debug("Emby stream cleanup: another worker won leader election, skipping auto-start")
        return

    logger.debug(f"Emby stream cleanup: won leader election (worker {worker_id})")

    # -- Clean stale state then start monitor ----------------------------------
    cleanup_stale_state(redis_client)

    if monitor.start(settings=settings_dict):
        logger.info("Emby stream cleanup: auto-start monitor successful")
    else:
        try:
            redis_client.delete(REDIS_KEY_LEADER)
        except Exception:
            pass
        logger.warning(
            "Emby stream cleanup: auto-start failed to start monitor. "
            "Use 'Start Monitor' button to start manually."
        )
        return

    # Optionally start the debug server
    if settings_dict.get("enable_debug_server", False):
        # Skip if debug server is already running (e.g. after force_reload)
        from .config import REDIS_KEY_RUNNING as _RRUN
        if redis_client.get(_RRUN):
            logger.debug("Emby stream cleanup: debug server already running (Redis), skipping")
        else:
            port = int(settings_dict.get('port', DEFAULT_PORT))
            host = normalize_host(
                settings_dict.get('host', DEFAULT_HOST),
                DEFAULT_HOST,
            )

            from .server import DebugServer
            server = DebugServer(monitor, port=port, host=host)
            if server.start(settings=settings_dict):
                logger.info(
                    f"Emby stream cleanup: auto-start debug server on http://{host}:{port}/debug"
                )
            else:
                logger.warning("Emby stream cleanup: auto-start debug server failed")
