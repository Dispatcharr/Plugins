"""
Stream Dripper — Dispatcharr plugin

Drops all active streams once per day at a configured time.
Also provides a manual "Drop Now" action.
"""

import fcntl
import logging
import os
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Process-scoped state — one scheduler thread per worker process.
_scheduler_thread = None
_stop_event = threading.Event()
_last_drop_date = None  # date object; set after a successful drop
_last_drop_info = {}    # summary of the most recent drop
_lock_fh = None         # held open for the lifetime of the scheduler process

_LOCK_PATH = "/tmp/stream-dripper-scheduler.lock"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_drop_time():
    """Read the configured drop_time from DB, falling back to the default."""
    try:
        from apps.plugins.models import PluginConfig
        cfg = PluginConfig.objects.get(key="stream-dripper")
        return (cfg.settings or {}).get("drop_time", "03:00")
    except Exception as e:
        logger.warning(f"stream-dripper: could not read drop_time from DB, using default 03:00: {e}")
        return "03:00"


def _drop_all_streams(log):
    """Stop every channel via the ORM + ChannelService. Returns a list of result dicts."""
    from apps.channels.models import Channel
    from apps.proxy.ts_proxy.services.channel_service import ChannelService

    uuids = list(Channel.objects.values_list("uuid", flat=True))
    if not uuids:
        log.info("stream-dripper: no channels in database, nothing to drop")
        return []

    results = []
    for uuid in uuids:
        try:
            result = ChannelService.stop_channel(str(uuid))
            if result.get("status") != "error":
                results.append({"channel_id": str(uuid), "result": result})
                log.info(f"stream-dripper: stopped channel {uuid}: {result.get('status')}")
        except Exception as e:
            log.error(f"stream-dripper: error stopping channel {uuid}: {e}")
            results.append({"channel_id": str(uuid), "error": str(e)})
    return results


def _save_last_drop(timestamp: str, channel_count: int, triggered_by: str):
    try:
        from apps.plugins.models import PluginConfig
        cfg = PluginConfig.objects.get(key="stream-dripper")
        settings = dict(cfg.settings or {})
        settings["last_drop"] = {
            "timestamp": timestamp,
            "channel_count": channel_count,
            "triggered_by": triggered_by,
        }
        cfg.settings = settings
        cfg.save(update_fields=["settings", "updated_at"])
    except Exception as e:
        logger.warning(f"stream-dripper: could not save last drop info to DB: {e}")


def _load_last_drop():
    try:
        from apps.plugins.models import PluginConfig
        cfg = PluginConfig.objects.get(key="stream-dripper")
        return (cfg.settings or {}).get("last_drop")
    except Exception:
        return None


def _scheduler_is_running():
    """Return True if any worker currently holds the scheduler lock."""
    try:
        fh = open(_LOCK_PATH, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()
        return False  # lock was free — no scheduler running
    except OSError:
        return True   # lock is held by another process


def _compute_next_drop(drop_time_str):
    """Return a human-readable string for the next scheduled drop time."""
    try:
        hour, minute = (int(p) for p in drop_time_str.split(":"))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return f"Unable to parse '{drop_time_str}'"


# ---------------------------------------------------------------------------
# Scheduler thread
# ---------------------------------------------------------------------------

def _scheduler_loop(stop_event):
    global _last_drop_date, _last_drop_info

    while not stop_event.wait(timeout=30):
        try:
            raw_time = _get_drop_time()
            hour, minute = (int(p) for p in raw_time.split(":"))

            now = datetime.now()
            drop_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            elapsed = (now - drop_today).total_seconds()

            logger.debug(
                f"stream-dripper: tick at {now.strftime('%H:%M:%S')}, "
                f"configured={raw_time}, elapsed={int(elapsed)}s, "
                f"last_drop={_last_drop_date}"
            )

            # Fire if we are within 5 minutes after the configured time and
            # haven't already dropped today.
            if 0 <= elapsed <= 300 and _last_drop_date != now.date():
                logger.info(
                    f"stream-dripper: daily drop triggered at {now.strftime('%H:%M:%S')} "
                    f"(configured {raw_time}, {int(elapsed)}s elapsed)"
                )
                results = _drop_all_streams(logger)
                _last_drop_date = now.date()
                _last_drop_info.update({
                    "timestamp": now.isoformat(),
                    "channel_count": len(results),
                    "triggered_by": "schedule",
                })
                _save_last_drop(now.isoformat(), len(results), "schedule")

        except Exception as e:
            logger.error(f"stream-dripper: unhandled error in scheduler loop: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class Plugin:
    name = "Stream Dripper"
    version = "1.0.0"
    description = (
        "Automatically drops all active streams once per day at a configured time, "
        "with a manual drop-now button."
    )
    author = "Megamannen"

    fields = [
        {
            "id": "drop_time",
            "label": "Daily Drop Time",
            "type": "select",
            "default": "03:00",
            "description": "Time each day to automatically drop all active streams.",
            "options": [
                {"value": f"{h:02d}:{m:02d}", "label": f"{h:02d}:{m:02d}"}
                for h in range(24)
                for m in (0, 15, 30, 45)
            ],
        },
    ]

    actions = [
        {
            "id": "drop_now",
            "label": "Drop All Streams Now",
            "description": "Immediately terminate all active streams.",
            "button_label": "Drop Now",
            "button_variant": "filled",
            "button_color": "red",
            "confirm": {
                "title": "Drop All Streams?",
                "message": (
                    "This will immediately terminate all active streams. "
                    "Clients will be disconnected. Continue?"
                ),
            },
        },
        {
            "id": "status",
            "label": "Scheduler Status",
            "description": "Show the current scheduler state and last drop information.",
            "button_label": "Status",
            "button_variant": "light",
            "button_color": "gray",
        },
    ]

    def __init__(self):
        global _scheduler_thread, _stop_event, _last_drop_date, _lock_fh

        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            logger.debug("stream-dripper: scheduler already running in this process, skipping")
            return

        # Acquire an exclusive non-blocking lock so only one worker process
        # runs the scheduler. The lock is held for the lifetime of the process;
        # it is released automatically if the process exits.
        try:
            fh = open(_LOCK_PATH, "w")
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fh = fh
        except OSError:
            logger.info("stream-dripper: another worker holds the scheduler lock, skipping")
            return

        _last_drop_date = None
        _stop_event = threading.Event()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(_stop_event,),
            daemon=True,
            name="stream-dripper-scheduler",
        )
        _scheduler_thread.start()
        logger.info("stream-dripper: scheduler thread started")

    def run(self, action: str, params: dict, context: dict):
        global _last_drop_date, _last_drop_info

        log = context.get("logger", logger)

        if action == "drop_now":
            results = _drop_all_streams(log)
            if not results:
                return {"status": "success", "message": "No active streams found. Nothing to drop."}

            now = datetime.now()
            _last_drop_date = now.date()
            _last_drop_info.update({
                "timestamp": now.isoformat(),
                "channel_count": len(results),
                "triggered_by": "manual",
            })
            _save_last_drop(now.isoformat(), len(results), "manual")
            errors = sum(1 for r in results if "error" in r)
            msg = f"Dropped {len(results) - errors} stream(s)"
            if errors:
                msg += f", {errors} error(s)"
            return {"status": "success", "message": msg}

        if action == "status":
            drop_time = _get_drop_time()
            now = datetime.now()
            return {
                "status": "success",
                "message": (
                    f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"Scheduler: {'running' if _scheduler_is_running() else 'stopped'} | "
                    f"Next drop: {_compute_next_drop(drop_time)}"
                ),
            }

        return {"status": "error", "message": f"Unknown action: {action}"}

    def stop(self, context: dict):
        global _scheduler_thread, _stop_event, _lock_fh

        log = context.get("logger", logger)
        log.info("stream-dripper: stop() called, signalling scheduler thread")
        _stop_event.set()
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=5)
        if _lock_fh is not None:
            try:
                fcntl.flock(_lock_fh, fcntl.LOCK_UN)
                _lock_fh.close()
            except Exception:
                pass
            _lock_fh = None
        log.info("stream-dripper: scheduler thread stopped")
