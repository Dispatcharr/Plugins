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
from .ffmpeg import _parse_resolution, fps_string

logger = logging.getLogger(__name__)

CHUNK_SIZE = 65536
_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compositor_worker.py")

_server_instance = None


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
    sig = [w for w in words if len(w) >= 2 and w.isupper()]
    if sig:
        return ("".join(sig) + "   ")[:3].lower()
    initials = "".join(w[0] for w in words if w)
    return (initials + "   ")[:3].lower()


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


def _audio_metadata_args(audio_source: str, channel_names: list, n: int) -> list:
    args = []
    if audio_source == "all":
        lang_codes = _deduplicate_lang_codes(channel_names or [])
        for i, (name, code) in enumerate(zip(channel_names or [], lang_codes)):
            args += [f"-metadata:s:a:{i}", f"title={name}",
                     f"-metadata:s:a:{i}", f"language={code}"]
    else:
        audio_idx = int(audio_source) if str(audio_source).isdigit() else 0
        audio_idx = max(0, min(audio_idx, n - 1))
        if channel_names and audio_idx < len(channel_names):
            name = channel_names[audio_idx]
            args += ["-metadata:s:a:0", f"title={name}",
                     "-metadata:s:a:0", f"language={_lang_code(name)}"]
    return args


def _usable_logo(url) -> "str | None":
    """Return url only if it's a local file path that exists on disk."""
    import os
    if url and isinstance(url, str) and url.startswith("/"):
        try:
            if os.path.isfile(url):
                return url
        except Exception:
            pass
    return None


def _channel_logo(ch) -> "str | None":
    """Local logo file path for a Channel, or None."""
    try:
        if getattr(ch, "logo_id", None) is not None:
            return _usable_logo(ch.logo.url)
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

    # ------------------------------------------------------------------ WSGI

    def wsgi_app(self, environ, start_response):
        path = environ.get("PATH_INFO", "")

        if path == "/health":
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"OK\n"]

        if path.startswith("/stream/"):
            try:
                n = int(path.split("/")[2])
            except (IndexError, ValueError):
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"Invalid stream index\n"]
            return self._serve_stream(n, start_response)

        if path.startswith("/internal/realsrc/"):
            return self._serve_realsrc(path[len("/internal/realsrc/"):], start_response)

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    # --------------------------------------------------------------- handlers

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
        proc = gsub.Popen(cmd, stdout=gsub.PIPE, stderr=gsub.PIPE)
        gevent.spawn(self._drain_stderr, proc, f"worker-{n}")

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ])
        return self._pump_stdout(proc, f"worker {n}")

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
        for i, (t, (x, y, w, h)) in enumerate(zip(tiles, rects)):
            tile_cfg.append({
                "url": f"http://127.0.0.1:{self.port}/internal/realsrc/{t['id']}",
                "x": x, "y": y, "w": w, "h": h,
                "logo": t.get("logo"), "name": t["name"],
                "audio": i in audio_idx,
                "lang": langs.get(i, "und"),
                "featured": featured_layout and i == 0,
            })

        return {
            "out_w": out_w, "out_h": out_h, "fps": fps_string(settings),
            "bitrate": int(settings.get("output_bitrate") or 8000),
            "preset": settings.get("encoder_preset") or "ultrafast",
            "tiles": tile_cfg,
        }

    def _pump_stdout(self, proc, label: str):
        try:
            while True:
                chunk = proc.stdout.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        except GeneratorExit:
            pass
        finally:
            try:
                proc.kill()
                proc.wait()
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

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("X-Accel-Buffering", "no"),
        ])
        return _dispatcharr.live_stream(channel_uuid)

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
            logger.error(f"Cannot bind to {self.host}:{self.port}: {e}")
            return False

        try:
            from gevent import pywsgi
            import gevent as _gevent

            def _run():
                try:
                    self._server = pywsgi.WSGIServer(
                        (self.host, self.port), self.wsgi_app, log=None,
                    )
                    self.running = True
                    set_server(self)
                    self._server.serve_forever()
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Multiview server crashed: {e}", exc_info=True)
                finally:
                    self.running = False

            self._greenlet = _gevent.spawn(_run)
            return True
        except ImportError:
            logger.error("gevent is not installed; cannot start multiview server")
            return False

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
