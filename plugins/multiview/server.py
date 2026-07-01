"""Multiview streaming server.

Routes (gevent pywsgi on the plugin port):

  GET /health                      Health check
  GET /stream/{n}                  Final multiview output for layout n (1-based).
                                   Builds a compositor.Compositor: one ffmpeg
                                   decoder per child -> numpy canvas -> one
                                   encoder -> MPEG-TS.
  GET /internal/realsrc/{channel_id}
                                   Live channel TS from Dispatcharr's proxy (see
                                   dispatcharr.live_stream); read by each tile's
                                   decoder and audio process.

The multiview output is itself a Dispatcharr channel, so Dispatcharr's live proxy
is the single client of /stream/{n} and fans out downstream; no client-sharing
logic is needed here.
"""

import json
import logging
import os
import re
import socket
import sys

from . import dispatcharr as _dispatcharr
from . import layouts as _layouts
from .parameters import resolve_preset

logger = logging.getLogger(__name__)

_FPS_CHOICES = {"24", "25", "30", "50", "60", "30000/1001", "60000/1001"}


def fps_string(settings: dict) -> str:
    v = str(settings.get("output_fps") or "30")
    return v if v in _FPS_CHOICES else "30"


def _parse_resolution(settings: dict) -> tuple:
    try:
        w, h = (int(x) for x in (settings.get("output_resolution") or "1920x1080").split("x"))
        return w, h
    except Exception:
        return 1920, 1080

CHUNK_SIZE = 65536
_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compositor_worker.py")

_server_instance = None
_dash_api = None


def _load_dash_api():
    """Load src/dash/api.py using the same file-path loader as other submodules."""
    global _dash_api
    if _dash_api is not None:
        return _dash_api
    import importlib.util
    import sys
    # Derive a stable module name from this module's own name
    parent = __name__.rsplit(".", 1)[0] if "." in __name__ else __name__
    mod_name = f"{parent}.dash_api"
    if mod_name in sys.modules:
        _dash_api = sys.modules[mod_name]
        return _dash_api
    api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dash", "api.py")
    spec = importlib.util.spec_from_file_location(mod_name, api_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _dash_api = mod
    return _dash_api


def _python_exe() -> str:
    """Path to a real python interpreter for the worker process.

    sys.executable is unreliable inside Dispatcharr's plugin host (it can resolve
    to a non-python launcher), so prefer python3/python on PATH.
    """
    import shutil
    cand = sys.executable
    if cand and os.path.basename(cand).startswith("python"):
        return cand
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return cand or "python3"


def get_server():
    return _server_instance


def set_server(s):
    global _server_instance
    _server_instance = s


def _settings() -> dict:
    try:
        from apps.plugins.models import PluginConfig
        return PluginConfig.objects.get(key="multiview").settings
    except Exception:
        return {}


# --- audio track labeling (unchanged; see lessons OLD notes) ------------------

def _lang_code(name: str) -> str:
    name = re.sub(r'^[A-Z0-9]{2,5}\s*[|–—-]\s*', '', name)
    clean = "".join(c for c in name if c.isalnum() or c == " ").strip()
    words = clean.split()
    if len(words) <= 1:
        return ((words[0] if words else "unk") + "   ")[:3].lower()
    parts = [w if (w.isupper() and len(w) >= 2) else w[0] for w in words]
    return ("".join(parts) + "   ")[:3].lower()


def _deduplicate_lang_codes(names: list) -> list:
    raw = [_lang_code(n) for n in names]
    counts: dict = {}
    for c in raw:
        counts[c] = counts.get(c, 0) + 1
    seen: dict = {}
    result = []
    for code in raw:
        if counts[code] > 1:
            seen[code] = seen.get(code, 0) + 1
            result.append(code[:2] + str(seen[code]))
        else:
            result.append(code)
    return result


def _channel_logo(ch) -> "str | None":
    """URL or path for the channel's logo, passable to av.open()."""
    try:
        if getattr(ch, "logo_id", None) is not None:
            url = ch.logo.url
            if url and isinstance(url, str):
                return url
    except Exception:
        pass
    return None


class MultiviewServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._server = None
        self._greenlet = None
        self.running = False
        self._active_procs: dict = {}  # proc -> layout_n

    # ------------------------------------------------------------------ WSGI

    def _loopback_only(self, loopback, start_response):
        if not loopback:
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"Forbidden\n"]
        return None

    def wsgi_app(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        loopback = environ.get("REMOTE_ADDR", "") in ("127.0.0.1", "::1")

        if path == "/health":
            if deny := self._loopback_only(loopback, start_response):
                return deny
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"OK\n"]

        is_dash_path = path == "/dash" or path.startswith("/dash/") or path.startswith("/api/")
        if is_dash_path and _settings().get("dash_enabled", "disabled") != "enabled":
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found\n"]

        if path.startswith("/dash/api/"):
            return self._handle_api(path[len("/dash"):], environ, start_response)

        if path == "/dash" or path.startswith("/dash/"):
            return _load_dash_api().serve_static(path if path.startswith("/dash/") else "/dash/", start_response)

        if path.startswith("/api/"):
            return self._handle_api(path, environ, start_response)

        if path.startswith("/stream/"):
            if deny := self._loopback_only(loopback, start_response):
                return deny
            try:
                n = int(path.split("/")[2])
            except (IndexError, ValueError):
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"Invalid stream index\n"]
            return self._serve_stream(n, start_response)

        if path.startswith("/internal/realsrc/"):
            if deny := self._loopback_only(loopback, start_response):
                return deny
            return self._serve_realsrc(path[len("/internal/realsrc/"):], start_response)

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    # --------------------------------------------------------------- handlers

    def _handle_api(self, path, environ, start_response):
        api = _load_dash_api()
        api._server = self  # inject current server so handlers can call kill_active_streams etc.
        if path == "/api/auth/token":
            return api.handle_auth_token(environ, start_response)
        if path == "/api/config":
            return api.handle_config(environ, start_response)
        if path == "/api/channels":
            return api.handle_channels(environ, start_response)
        if path == "/api/fields":
            return api.handle_fields(environ, start_response)
        if path == "/api/refresh":
            return api.handle_refresh(environ, start_response)
        if path == "/api/streams":
            return api.handle_streams_list(environ, start_response)
        if path == "/api/streams/restart":
            return api.handle_streams_restart(environ, start_response)
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    def _serve_stream(self, n: int, start_response):
        logger.info(f"Stream request: layout {n}")
        try:
            tiles, layout, audio_source = self._resolve_layout(n)
        except LookupError as e:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [str(e).encode()]
        except Exception as e:  # noqa: BLE001
            logger.error(f"Layout {n} error: {e}", exc_info=True)
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"error\n"]

        from . import deps as _deps
        arch = _deps.detect_arch()
        if not arch or not _deps.pyav_status(arch):
            logger.warning(f"Stream {n}: PyAV not installed for {arch or 'this arch'}")
            start_response("503 Service Unavailable", [("Content-Type", "text/plain")])
            return [(f"PyAV media engine not installed for {arch or 'this CPU arch'}. "
                     f"Open the Multiview plugin settings and run the 'Install PyAV' "
                     f"action, then retry.\n").encode()]

        settings = _settings()
        cfg = self._worker_config(tiles, layout, audio_source, settings)
        cmd = [_python_exe(), _WORKER, json.dumps(cfg)]
        logger.info(f"Starting compositor worker: {len(tiles)} tiles, layout={layout}, "
                    f"audio={audio_source}, {cfg['out_w']}x{cfg['out_h']}@{cfg['fps']}")

        import gevent
        import gevent.subprocess as gsub
        proc = gsub.Popen(cmd, stdin=gsub.PIPE, stdout=gsub.PIPE, stderr=gsub.PIPE)
        stderr_gl = gevent.spawn(self._drain_stderr, proc, f"worker-{n}")
        self._active_procs[proc] = {"n": n, "cfg": cfg}

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ])
        return self._pump_stdout(proc, f"worker {n}", stderr_gl)

    def _worker_config(self, tiles, layout, audio_source, settings) -> dict:
        out_w, out_h = _parse_resolution(settings)
        rects = _layouts.tile_rects(layout, len(tiles), out_w, out_h)
        names = [t["name"] for t in tiles]

        # Which tiles contribute an audio track, and their language codes.
        if audio_source == "all":
            audio_idx = set(range(len(tiles)))
            langs = dict(zip(range(len(tiles)), _deduplicate_lang_codes(names)))
        else:
            ai = int(audio_source) if str(audio_source).isdigit() else 0
            ai = max(0, min(ai, len(tiles) - 1))
            audio_idx = {ai}
            langs = {ai: _lang_code(names[ai])}

        # Only the main tile of a featured layout is "featured" (full-effort
        # decode); every other tile (whole auto grid, or the small side/bottom
        # tiles) decodes at lower effort to save CPU.
        featured_layout = layout in ("featured", "top_featured")
        tile_cfg = []
        for i, (t, (x, y, w, h, valign, halign)) in enumerate(zip(tiles, rects)):
            tile_cfg.append({
                "url": f"http://127.0.0.1:{self.port}/internal/realsrc/{t['id']}",
                "x": x, "y": y, "w": w, "h": h,
                "logo": t.get("logo"), "name": t["name"],
                "audio": i in audio_idx,
                "lang": langs.get(i, "und"),
                "featured": featured_layout and i == 0,
                "valign": valign, "halign": halign,
            })

        encoder = settings.get("video_encoder") or "libx264"
        preset = resolve_preset(encoder, settings.get("encoder_preset"))
        return {
            "out_w": out_w, "out_h": out_h, "fps": fps_string(settings),
            "bitrate": int(settings.get("output_bitrate") or 8000),
            "preset": preset,
            "video_encoder": encoder,
            "tiles": tile_cfg,
        }

    def get_active_streams(self) -> list:
        seen = {}
        for info in self._active_procs.values():
            n = info["n"]
            if n not in seen:
                tiles = info["cfg"].get("tiles", [])
                seen[n] = {"n": n, "channels": [{"idx": i, "name": t.get("name", f"Channel {i+1}")} for i, t in enumerate(tiles)]}
        return [seen[n] for n in sorted(seen)]

    def kill_active_streams(self) -> int:
        procs = list(self._active_procs)
        for proc in procs:
            try:
                proc.kill()
            except Exception:
                pass
        return len(procs)

    def kill_stream(self, n: int) -> int:
        to_kill = [p for p, info in list(self._active_procs.items()) if info["n"] == n]
        for proc in to_kill:
            try:
                proc.kill()
            except Exception:
                pass
        return len(to_kill)

    def reconnect_channel(self, n: int, idx: int) -> bool:
        import json as _json
        for proc, info in list(self._active_procs.items()):
            if info["n"] == n:
                try:
                    cmd = _json.dumps({"cmd": "reconnect_channel", "idx": idx}).encode() + b"\n"
                    proc.stdin.write(cmd)
                    proc.stdin.flush()
                    return True
                except Exception:
                    pass
        return False

    def _pump_stdout(self, proc, label: str, stderr_gl=None):
        try:
            while True:
                chunk = proc.stdout.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        except GeneratorExit:
            pass
        finally:
            self._active_procs.pop(proc, None)
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
            if stderr_gl is not None:
                try:
                    stderr_gl.kill(block=False)
                except Exception:
                    pass
            logger.info(f"{label} ended, worker killed")

    def _drain_stderr(self, proc, label: str):
        try:
            for raw in proc.stderr:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    logger.warning(f"{label}: {line}")
        except Exception:
            pass

    def _serve_realsrc(self, raw_id: str, start_response):
        channel_uuid = _dispatcharr.resolve_channel_uuid(raw_id)
        if channel_uuid is None:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Unknown channel\n"]

        # Retry briefly while the live_proxy warms up the channel after container
        # start. live_stream() cleans up its client registration in its finally
        # block before raising StopIteration, so retrying is safe. Keep retries
        # low (2) to avoid spamming logs when a channel is genuinely unavailable.
        first = None
        gen = None
        for attempt in range(3):
            gen = _dispatcharr.live_stream(channel_uuid)
            try:
                first = next(gen)
                break
            except StopIteration:
                if attempt < 2:
                    try:
                        import gevent as _gv
                        _gv.sleep(1.0)
                    except ImportError:
                        import time as _t
                        _t.sleep(1.0)
                else:
                    start_response("503 Service Unavailable", [("Content-Type", "text/plain")])
                    return [b"Channel not ready\n"]

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ])
        def _body():
            try:
                yield first
                yield from gen
            finally:
                gen.close()
        return _body()

    # --------------------------------------------------------------- helpers

    def _resolve_layout(self, n: int):
        """Return (tiles, layout, audio_source).

        tiles: list of {"id": channel_id, "name": str, "logo": str|None}. At
        least 2 required.
        """
        from apps.plugins.models import PluginConfig
        from apps.channels.models import Channel

        try:
            settings = PluginConfig.objects.get(key="multiview").settings
        except Exception:
            settings = {}

        ch_count = max(2, int(settings.get(f"multiview_{n}_channel_count", 4)))
        layout = settings.get(f"multiview_{n}_layout", "auto")
        selector_type = settings.get(f"multiview_{n}_selector_type", "classic")

        tiles = []
        if selector_type == "regex":
            pattern = settings.get(f"multiview_{n}_regex_pattern", "").strip()
            if not pattern:
                raise LookupError(f"Layout {n} is in regex mode but has no pattern configured")
            matched = list(
                Channel.objects.select_related("logo").filter(name__iregex=pattern)
                .order_by("channel_number")[:ch_count]
            )
            for ch in matched:
                tiles.append({"id": ch.id, "name": ch.name, "logo": _channel_logo(ch)})
            audio_source = settings.get(f"multiview_{n}_audio_source", "0")
            if audio_source in ("regex_first", "regex_lowest"):
                audio_source = "0"
        else:
            for m in range(1, ch_count + 1):
                ch_id_str = settings.get(f"multiview_{n}_channel_{m}", "_none")
                if not ch_id_str or ch_id_str == "_none":
                    continue
                try:
                    ch = Channel.objects.select_related("logo").get(id=int(ch_id_str))
                except Channel.DoesNotExist:
                    logger.warning(f"Layout {n} slot {m}: id={ch_id_str} not found, skipping")
                    continue
                tiles.append({"id": ch.id, "name": ch.name, "logo": _channel_logo(ch)})
            audio_source = settings.get(f"multiview_{n}_audio_source", "0")

        if len(tiles) < 2:
            raise LookupError(
                f"Layout {n} needs at least 2 configured channels (found {len(tiles)})"
            )

        logger.info(f"Layout {n}: {len(tiles)} channels, layout={layout}, audio={audio_source}")
        return tiles, layout, audio_source

    # ------------------------------------------------------------- lifecycle

    def start(self) -> bool:
        if self.running:
            logger.warning("Multiview server is already running")
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.close()
        except OSError as e:
            logger.info(f"Multiview: port {self.port} already taken, skipping ({e})")
            return False

        try:
            from gevent import pywsgi
            import gevent as _gevent
        except ImportError:
            logger.error("gevent is not installed; cannot start multiview server")
            return False

        def _run():
            try:
                self._server = pywsgi.WSGIServer(
                    (self.host, self.port), self.wsgi_app, log=None,
                )
                self.running = True
                set_server(self)
                self._server.serve_forever()
            except OSError as e:
                # EADDRINUSE here means a concurrent worker won the race between
                # our test-bind above and this re-bind -- expected on multi-worker
                # startup, not an error.
                logger.info(f"Multiview: port {self.port} taken by concurrent worker ({e})")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Multiview server crashed: {e}", exc_info=True)
            finally:
                self.running = False

        self._greenlet = _gevent.spawn(_run)
        return True

    def stop(self):
        if self._server:
            try:
                self._server.stop()
            except Exception:
                pass
        self.running = False
        set_server(None)
        logger.info("Multiview server stopped")

    def is_running(self) -> bool:
        return self.running
