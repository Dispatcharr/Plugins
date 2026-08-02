"""Self-elected, file-lock-based periodic scheduler.

Dispatcharr plugins cannot use django_celery_beat/PeriodicTask for
scheduled work: plugin modules are imported dynamically, after the
Celery worker has already built its task dispatch table, so
beat-triggered plugin tasks always fail as unregistered (confirmed via
the merged m3u-expiration-notifier plugin's own code comment describing
exactly this failure mode). Since Dispatcharr runs multiple processes
(web/daphne, celery worker, celery beat) with no shared memory, a single
periodic sync instead requires one process to elect itself via an
atomic lock file and run an in-process background thread. This mirrors
that plugin's proven approach.
"""

import json
import os
import threading
import time
import uuid

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

LOCK_FILE = os.path.join(_PLUGIN_DIR, "scheduler.pid")
NEXT_RUN_FILE = os.path.join(_PLUGIN_DIR, "scheduler_next_run.json")
RELOAD_FLAG = os.path.join(_PLUGIN_DIR, "scheduler_reload.flag")
STOP_FLAG = os.path.join(_PLUGIN_DIR, "scheduler_stop.flag")

POLL_SECONDS = 30
INELIGIBLE_HOST_MARKERS = ("daphne", "dispatcharr.asgi")


def _is_ineligible_host():
    try:
        with open("/proc/self/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", "replace")
    except Exception:
        return False
    return any(marker in cmdline for marker in INELIGIBLE_HOST_MARKERS)


class Scheduler:
    def __init__(self, get_settings, run_sync_fn, logger):
        self._get_settings = get_settings
        self._run_sync_fn = run_sync_fn
        self._logger = logger
        self._thread = None
        self._stop_event = threading.Event()
        self._holds_lock = False

    # -- locking ---------------------------------------------------------

    def _lock_is_stale(self):
        try:
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
            pid = int(content.split(":", 1)[0])
        except Exception:
            return True
        if pid == os.getpid():
            return False
        try:
            os.kill(pid, 0)
            return False
        except ProcessLookupError:
            return True
        except PermissionError:
            return False

    def _acquire_lock(self):
        payload = f"{os.getpid()}:{uuid.uuid4().hex}".encode()
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            if self._lock_is_stale():
                try:
                    os.remove(LOCK_FILE)
                except OSError:
                    return False
                return self._acquire_lock()
            return False

    def _release_lock(self):
        if not self._holds_lock:
            return
        try:
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
            if content.startswith(f"{os.getpid()}:"):
                os.remove(LOCK_FILE)
        except Exception:
            pass
        self._holds_lock = False

    # -- persisted schedule state -----------------------------------------

    def _configured_interval_minutes(self):
        try:
            return max(0, int(self._get_settings().get("sync_interval_minutes") or 0))
        except (TypeError, ValueError):
            return 0

    def _read_next_run(self):
        try:
            with open(NEXT_RUN_FILE, "r") as f:
                return float(json.load(f).get("next_run") or 0)
        except Exception:
            return 0.0

    def _write_next_run(self, ts):
        try:
            with open(NEXT_RUN_FILE, "w") as f:
                json.dump({"next_run": ts}, f)
        except Exception:
            self._logger.debug("LDAP User Sync: failed to persist next_run", exc_info=True)

    @staticmethod
    def _consume_flag(path):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
            return True
        return False

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        if _is_ineligible_host():
            return
        if not self._acquire_lock():
            return
        self._holds_lock = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        from django.db import close_old_connections

        interval_minutes = self._configured_interval_minutes()
        next_run = self._read_next_run()
        if interval_minutes and not next_run:
            next_run = time.time() + interval_minutes * 60
            self._write_next_run(next_run)

        while not self._stop_event.is_set():
            if self._consume_flag(STOP_FLAG):
                break
            if self._consume_flag(RELOAD_FLAG):
                interval_minutes = self._configured_interval_minutes()
                next_run = (time.time() + interval_minutes * 60) if interval_minutes else 0
                self._write_next_run(next_run)

            interval_minutes = self._configured_interval_minutes()
            if interval_minutes and next_run and time.time() >= next_run:
                try:
                    settings = self._get_settings()
                    summary = self._run_sync_fn(
                        settings, self._logger, dry_run=bool(settings.get("dry_run_mode"))
                    )
                    self._logger.info("LDAP User Sync: scheduled sync complete: %s", summary)
                except Exception:
                    self._logger.exception("LDAP User Sync: scheduled sync failed")
                finally:
                    close_old_connections()
                next_run = time.time() + interval_minutes * 60
                self._write_next_run(next_run)

            self._stop_event.wait(POLL_SECONDS)

    def request_reload(self):
        try:
            open(RELOAD_FLAG, "a").close()
        except OSError:
            pass

    def next_run_at(self):
        return self._read_next_run()

    def stop(self):
        self._stop_event.set()
        try:
            open(STOP_FLAG, "a").close()
        except OSError:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._release_lock()
