"""Auto-start logic for the Prometheus Exporter metrics server.

Replaces the old file-lock (flock / /tmp) mechanism with Redis leader election:

  1. Each uWSGI worker calls ``attempt_autostart()`` from ``Plugin.__init__``.
     A per-process guard ensures only one thread is spawned per process.

  2. The background thread waits for the Django ORM to be ready, then reads
     the plugin config.  If ``auto_start`` is disabled it exits immediately.

  3. It races all other workers with a Redis ``SET NX EX`` on a leader key.
     Only the winner proceeds; all others exit cleanly.

  4. The winner clears any stale Redis state left from a previous lifecycle,
     then starts the MetricsServer.

The per-process guard ``_autostart_launched`` prevents spawning duplicate
threads *within a single import cycle*, but ``force_reload=True`` in
Dispatcharr's plugin loader re-imports all modules, resetting module-level
state.  To handle that, the autostart thread also checks Redis for an
already-running server before doing anything destructive.

No /tmp files, no flock(), no global retry counters.
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


def attempt_autostart(collector) -> None:
    """Entry point from ``Plugin.__init__``.

    Spawns a daemon thread (at most once per OS process) that races via Redis
    NX to become the autostart leader and start the metrics server.
    """
    global _autostart_launched
    with _autostart_lock:
        if _autostart_launched:
            logger.debug("Prometheus exporter: auto-start already launched in this process, skipping")
            return
        _autostart_launched = True

    # Redis-level dedup is handled later inside the background thread
    # (leader election). We avoid touching Redis here because Plugin.__init__
    # runs at import time, potentially before Dispatcharr's Redis is ready.
    # Blocking here would stall the entire uWSGI worker boot.

    threading.Thread(
        target=_autostart_worker,
        args=(collector,),
        daemon=True,
        name="prometheus-autostart",
    ).start()


def cleanup_stale_state(redis_client) -> None:
    """Delete plugin Redis keys left over from a previous container lifecycle.

    The leader key is intentionally *not* deleted here so the winning worker
    retains its claim throughout the startup sequence.
    """
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


def _autostart_worker(collector) -> None:
    """Background thread body."""
    from .config import REDIS_KEY_LEADER, REDIS_KEY_RUNNING, LEADER_TTL, DEFAULT_PORT, DEFAULT_HOST, AUTO_START_DEFAULT, PLUGIN_DB_KEY
    from .utils import get_redis_client, normalize_host

    # ── Step 0: Redis dedup (prevents redundant threads after force_reload) ──
    # This runs inside the thread (after the daemon is spawned) so it never
    # blocks uWSGI worker boot.  The initial sleep gives Redis time to be ready.
    time.sleep(_STARTUP_WAIT)
    try:
        _rc = get_redis_client()
        if _rc:
            _dedup_key = REDIS_KEY_LEADER + ":autostart_dedup"
            if not _rc.set(_dedup_key, "1", nx=True, ex=(_RETRY_DELAY * _MAX_ATTEMPTS) + 30):
                # Key exists — but if nothing is actually running or leading,
                # it's stale from a previous lifecycle.  Clear and proceed.
                if not _rc.get(REDIS_KEY_RUNNING) and not _rc.get(REDIS_KEY_LEADER):
                    logger.debug("Prometheus exporter: stale autostart_dedup key, clearing")
                    _rc.delete(_dedup_key)
                    _rc.set(_dedup_key, "1", nx=True, ex=(_RETRY_DELAY * _MAX_ATTEMPTS) + 30)
                else:
                    logger.debug("Prometheus exporter: auto-start already in progress (Redis dedup), skipping")
                    return
    except Exception:
        pass  # Redis not available yet — proceed, leader election will gate us

    # ── Step 1: wait for Django ORM and read plugin config ───────────────────
    # Try both key forms since Dispatcharr derives the DB key from the zip
    # folder name, which may use underscores or hyphens depending on build source.
    _plugin_keys = [PLUGIN_DB_KEY, PLUGIN_DB_KEY.replace('_', '-')]

    settings_dict: dict = {}
    auto_start_enabled = False

    for attempt in range(_MAX_ATTEMPTS):
        # First iteration has no sleep — _STARTUP_WAIT already elapsed above.
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
                    f"Prometheus exporter: PluginConfig not found yet "
                    f"(attempt {attempt + 1}/{_MAX_ATTEMPTS}, tried keys: {_plugin_keys})"
                )
                continue
            settings_dict = config.settings or {}
            auto_start_enabled = bool(
                config.enabled
                and settings_dict.get('auto_start', AUTO_START_DEFAULT)
            )
            logger.debug(
                f"Prometheus exporter: auto-start config read on attempt {attempt + 1}: "
                f"plugin_enabled={config.enabled}, auto_start={auto_start_enabled}"
            )
            break
        except Exception as e:
            logger.debug(
                f"Prometheus exporter: auto-start attempt {attempt + 1} could not read config: {e}"
            )
    else:
        logger.warning(
            "Prometheus exporter: could not read plugin config after all attempts, aborting auto-start"
        )
        return

    if not auto_start_enabled:
        logger.debug("Prometheus exporter: auto-start disabled in settings")
        return

    # ── Step 1b: respect manual stop ─────────────────────────────────────────
    # If the user manually stopped the server during this Dispatcharr runtime,
    # a Redis flag is set.  It's cleared on fresh boot (CLEANUP_REDIS_KEYS).
    try:
        from .config import REDIS_KEY_MANUAL_STOP
        _rc = get_redis_client()
        if _rc and _rc.get(REDIS_KEY_MANUAL_STOP):
            logger.debug("Prometheus exporter: auto-start skipped (server was manually stopped)")
            return
    except Exception:
        pass

    # ── Step 2: leader election via Redis SET NX ─────────────────────────────
    redis_client = get_redis_client()
    if redis_client is None:
        logger.warning("Prometheus exporter: cannot connect to Redis, aborting auto-start")
        return

    # Guard: if the server is already running (e.g. we were force-reloaded
    # and the old daemon thread is still alive), skip everything.  This
    # prevents cleanup_stale_state from nuking keys for a live server.
    if redis_client.get(REDIS_KEY_RUNNING):
        logger.debug("Prometheus exporter: server already running (Redis), skipping auto-start")
        return

    worker_id = f"{os.getpid()}-{threading.get_ident()}"
    won = redis_client.set(REDIS_KEY_LEADER, worker_id, nx=True, ex=LEADER_TTL)
    if not won:
        logger.debug("Prometheus exporter: another worker won leader election, skipping auto-start")
        return

    logger.debug(f"Prometheus exporter: won leader election (worker {worker_id})")

    # ── Step 3: clean stale state then start server ──────────────────────────
    # Cleanup happens *after* winning leader election so only one worker does
    # it and the leader key is never touched (preserving our claim).
    cleanup_stale_state(redis_client)

    port = int(settings_dict.get('port', DEFAULT_PORT))
    host = normalize_host(
        settings_dict.get('host', DEFAULT_HOST),
        DEFAULT_HOST,
    )

    from .server import MetricsServer
    server = MetricsServer(collector, port=port, host=host)
    if server.start(settings=settings_dict):
        logger.info(
            f"Prometheus exporter: auto-start successful on http://{host}:{port}/metrics"
        )
    else:
        # Release leadership so the user can start manually via the UI button.
        try:
            redis_client.delete(REDIS_KEY_LEADER)
        except Exception:
            pass
        logger.warning(
            "Prometheus exporter: auto-start failed to start server. "
            "Use 'Start Metrics Server' button to start manually."
        )
