"""Auto-start logic for the Emby Stream Cleanup monitor and dashboard server.

Mirrors force-fallback/multiview's autostart pattern: cheap, safe to call
every time ``Plugin()`` is constructed (which Dispatcharr does repeatedly
over the plugin's lifecycle -- e.g. on settings-page loads -- not just once
at boot), so a single missed window (DB or Redis not ready yet) just means
the *next* construction tries again shortly, rather than giving up forever.

The monitor and the dashboard server must always end up in the **same**
worker process: the dashboard reads live state via ``dash/api.py``'s
``_find_plugin_module()``, which only scans ``sys.modules`` in its own
process to find the module-level ``_monitor`` singleton. If the dashboard
binds its port in a different worker than the one actually running the
monitor's poll loop, it finds an idle ``_monitor`` that was never
``.start()``-ed and reports empty/stopped state forever.

- Monitor autostart uses Redis leader election (SET NX EX): the monitor is a
  bare background thread with no OS-level exclusivity guarantee, so an
  explicit single-owner election across Dispatcharr's worker processes is
  needed to avoid duplicate polling loops. It must run continuously
  regardless of whether the dashboard is even enabled, so it stays the
  primary election.
- Dashboard server autostart is now a **dependent** of the monitor, not an
  independent race: ``ensure_dashboard`` only ever does anything when
  ``monitor.is_running()`` is ``True`` for *this* process, i.e. only in the
  worker that already won the monitor's leader election. This guarantees
  dashboard and monitor always share a process. It's called both here (fast
  path, on the ``Plugin()`` construction that wins leader election) and from
  the monitor's own poll loop (``handler.py:_poll_loop``) on every cycle, so
  the dashboard no longer depends on ``Plugin()`` being reconstructed again
  to retry a failed bind -- the poll loop is proven alive for as long as the
  monitor runs.

This repo has one earlier regression to avoid repeating here: dashboard-start
used to run only after a *successful* monitor leader-election win, physically
inside the same function. That meant once the monitor was running from any
earlier attempt on any worker, every later ``attempt_autostart()`` call --
including the leader's own subsequent calls -- returned early at a **Redis**
check ("is the monitor running anywhere?") before ever reaching the
dashboard-start code, so only the one attempt that originally won leader
election ever got a shot at binding the dashboard port. The gate here is
different in the way that matters: ``monitor.is_running()`` is a **local,
in-process** attribute read on the actual ``StreamMonitor`` object, true only
in the one process that called ``.start()`` successfully. It never blocks
that process's own repeated ``Plugin()`` constructions from retrying the
dashboard bind -- it only ever prevents *other* workers (which aren't running
the monitor at all) from attempting it.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

# Debounces a burst of near-simultaneous Plugin() constructions (e.g. several
# requests landing at once) from spawning a pile of redundant autostart
# threads. Transient, not a permanent lock: always cleared when an attempt
# finishes (success, failure, or exception), so the *next* Plugin()
# construction gets a fresh, un-gated try.
_attempt_in_progress = False
_attempt_lock = threading.Lock()

# Dedupes repeated identical autostart-worker exceptions so they log at
# `warning` once (visible without debug logging) rather than spamming on
# every retry -- see _autostart_worker.
_last_autostart_error = None


def attempt_autostart(monitor) -> None:
    """Entry point from ``Plugin.__init__``.

    Safe, and intended, to call on every ``Plugin()`` construction -- cheap
    early-outs below mean a monitor/dashboard that's already running (locally
    or, for the monitor, on another worker) costs almost nothing to check.
    """
    global _attempt_in_progress
    with _attempt_lock:
        if _attempt_in_progress:
            logger.debug("Emby stream cleanup: an auto-start attempt is already in flight, skipping")
            return
        _attempt_in_progress = True

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


def _read_plugin_settings():
    """Read current PluginConfig settings.

    Returns (settings_dict, enabled), or (None, None) if the DB/ORM isn't
    ready yet or the row doesn't exist -- callers should just bail and let
    the next Plugin() construction retry, not treat this as fatal.
    """
    from .config import PLUGIN_DB_KEY
    try:
        from apps.plugins.models import PluginConfig
        config = None
        for _key in (PLUGIN_DB_KEY, PLUGIN_DB_KEY.replace('_', '-')):
            config = PluginConfig.objects.filter(key=_key).first()
            if config is not None:
                break
        if config is None:
            return None, None
        return (config.settings or {}), config.enabled
    except Exception:
        return None, None


def _autostart_worker(monitor) -> None:
    global _attempt_in_progress, _last_autostart_error
    try:
        settings_dict, enabled = _read_plugin_settings()
        if settings_dict is None:
            logger.debug("Emby stream cleanup: PluginConfig not found yet, will retry on next Plugin() construction")
            return
        if not enabled:
            logger.debug("Emby stream cleanup: plugin is disabled, skipping auto-start")
            return

        _try_autostart_monitor(monitor, settings_dict)
        if monitor.is_running():
            # Dashboard only ever starts in the same process that's running
            # the monitor -- see module docstring for why. The monitor's own
            # poll loop (handler.py:_poll_loop) also calls ensure_dashboard
            # every cycle as a self-healing backstop, so this call here is
            # just the fast path on the construction that won leader election.
            ensure_dashboard(monitor, settings_dict)
        _last_autostart_error = None
    except Exception as e:  # noqa: BLE001
        err = str(e)
        if err != _last_autostart_error:
            logger.warning(f"Emby stream cleanup: auto-start attempt raised, will retry on next Plugin() construction: {e}")
            _last_autostart_error = err
        else:
            logger.debug(f"Emby stream cleanup: auto-start attempt raised again (already warned): {e}")
    finally:
        _attempt_in_progress = False


def _try_autostart_monitor(monitor, settings_dict: dict) -> None:
    from .config import REDIS_KEY_LEADER, REDIS_KEY_MONITOR, REDIS_KEY_MANUAL_STOP, LEADER_TTL
    from .utils import get_redis_client

    if monitor.is_running():
        return  # already running in this process

    # -- Require at least one fully configured media server -------------------
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
        logger.debug(
            "Emby stream cleanup: monitor auto-start skipped, no media server is fully "
            "configured yet (URL + API key + identifier) -- will retry on next Plugin() construction"
        )
        return

    redis_client = get_redis_client()
    if redis_client is None:
        logger.debug("Emby stream cleanup: cannot connect to Redis yet, will retry on next Plugin() construction")
        return

    # -- Respect a manual stop from earlier in this Dispatcharr runtime -------
    # Cleared on fresh container boot (CLEANUP_REDIS_KEYS).
    if redis_client.get(REDIS_KEY_MANUAL_STOP):
        logger.debug("Emby stream cleanup: monitor auto-start skipped (manually stopped)")
        return

    # Guard: if the monitor is already running (e.g. on another worker, or
    # this worker was force-reloaded and the old daemon thread is still
    # alive), skip everything -- this also prevents cleanup_stale_state from
    # nuking keys for a live server.
    if redis_client.get(REDIS_KEY_MONITOR):
        logger.debug("Emby stream cleanup: monitor already running (Redis), skipping monitor auto-start")
        return

    # -- Leader election via Redis SET NX --------------------------------------
    worker_id = f"{os.getpid()}-{threading.get_ident()}"
    won = redis_client.set(REDIS_KEY_LEADER, worker_id, nx=True, ex=LEADER_TTL)
    if not won:
        logger.debug("Emby stream cleanup: another worker won leader election, skipping monitor auto-start")
        return

    logger.debug(f"Emby stream cleanup: won leader election (worker {worker_id})")

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
            "Use 'Restart Monitor' to start manually."
        )


def ensure_dashboard(monitor, settings_dict: dict) -> None:
    """Local-only, no Redis -- matches force-fallback/multiview's dashboard
    server autostart. Only ever meaningful (see callers) when
    ``monitor.is_running()`` is already ``True`` for this process, i.e. this
    worker just won -- or previously won -- the monitor's Redis leader
    election. That keeps the dashboard and the monitor's poll loop pinned to
    the same process, which is what lets ``dash/api.py``'s in-process
    ``sys.modules`` lookup find a live ``_monitor`` instead of an idle one.

    Cheap and idempotent: short-circuits immediately once
    ``get_current_server().is_running()`` is true, so it's safe to call
    repeatedly (both from ``_autostart_worker`` on each ``Plugin()``
    construction, and from the monitor's own poll loop as a self-healing
    backstop that doesn't depend on ``Plugin()`` being reconstructed again).
    """
    from .config import DEFAULT_PORT, DEFAULT_HOST
    from .utils import normalize_host

    if settings_dict.get("dash_enabled") != "enabled":
        return

    from .server import get_current_server, DebugServer
    existing = get_current_server()
    if existing and existing.is_running():
        logger.debug("Emby stream cleanup: dashboard server already running in this process, skipping")
        return

    port = int(settings_dict.get('dash_port', DEFAULT_PORT))
    host = normalize_host(settings_dict.get('dash_host', DEFAULT_HOST), DEFAULT_HOST)

    server = DebugServer(monitor, port=port, host=host)
    if server.start():
        path = settings_dict.get('dash_path') or '/dash'
        logger.info(f"Emby stream cleanup: auto-start dashboard on http://{host}:{port}{path}/")
    else:
        logger.debug("Emby stream cleanup: dashboard auto-start bind failed (port likely taken by another worker)")
