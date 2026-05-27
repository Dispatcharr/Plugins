"""Multiview streaming server.

Runs a lightweight gevent WSGI server. Each /stream/{n} request spawns an
ffmpeg subprocess that tiles the configured channels and pipes MPEG-TS output
back to the client. The subprocess is killed when the client disconnects.
Zero ffmpeg processes run when nobody is watching.

Each channel is opened via Dispatcharr's ProxyServer internal API so that
full fallback/profile behaviour is respected and connections appear in the
Dispatcharr stats view with user-agent "multiview-plugin".

Routes:
  GET /health              Health check
  GET /stream/{n}          MPEG-TS multiview stream for layout n (1-based)
  GET /internal/ch/{uuid}  Internal per-channel TS feed consumed by ffmpeg
"""

import logging
import math
import os
import re
import socket
import subprocess
import threading
import uuid as _uuid_module

from . import layouts as _layouts

logger = logging.getLogger(__name__)

# MPEG-TS null packets (PID 0x1FFF): transparent to every decoder,
# used to keep the connection alive between placeholder end and real start.
_NULL_TS_BURST = (bytes([0x47, 0x1F, 0xFF, 0x10]) + bytes(184)) * 7

_server_instance = None


def get_server() -> "MultiviewServer | None":
    return _server_instance


def set_server(s):
    global _server_instance
    _server_instance = s


def _log_stderr(proc, label):
    try:
        for raw in proc.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                logger.warning(f"ffmpeg {label}: {line}")
    except Exception:
        pass


def _usable_logo(url: str | None) -> str | None:
    """Return url only if it's a local file path that exists on disk."""
    if url and url.startswith("/"):
        try:
            if os.path.isfile(url):
                return url
        except Exception:
            pass
    return None


def _lang_code(name: str) -> str:
    """Derive a 3-char lowercase language tag from a channel name for MPEG-TS PMT."""
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


def _deduplicate_lang_codes(names: list[str]) -> list[str]:
    """Return lang codes for names, replacing the 3rd char with a 1-based index for duplicates.

    e.g. ['TSN 1', 'TSN 2', 'TSN 3'] -> ['ts1', 'ts2', 'ts3']
    """
    raw = [_lang_code(n) for n in names]
    counts: dict[str, int] = {}
    for c in raw:
        counts[c] = counts.get(c, 0) + 1
    seen: dict[str, int] = {}
    result = []
    for code in raw:
        if counts[code] > 1:
            seen[code] = seen.get(code, 0) + 1
            result.append(code[:2] + str(seen[code]))
        else:
            result.append(code)
    return result


def _parse_resolution(settings: dict) -> tuple[int, int]:
    try:
        w, h = (int(x) for x in (settings.get("output_resolution") or "1920x1080").split("x"))
        return w, h
    except Exception:
        return 1920, 1080


def _kill_proc(proc) -> None:
    try:
        proc.kill()
        proc.wait()
    except Exception:
        pass


def _gevent_sleep():
    try:
        import gevent
        return gevent.sleep
    except ImportError:
        import time
        return time.sleep


def _gevent_popen():
    try:
        import gevent.subprocess as _gsp
        return _gsp.Popen
    except ImportError:
        return subprocess.Popen


def _audio_metadata_args(audio_source: str, channel_names: list[str], n: int) -> list:
    """Return -metadata:s:a:i args for audio track title and language."""
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


def _single_channel_placeholder_gen(channel_id, channel_name: str, logo_url, proxy_server):
    """Yield MPEG-TS logo placeholder until channel_id's buffer is available again."""
    _Popen = _gevent_popen()

    usable = _usable_logo(logo_url)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning",
           "-f", "lavfi", "-i", "color=c=black:size=320x180:r=30000/1001",
           "-f", "lavfi", "-i", "aevalsrc=0:sample_rate=48000:channel_layout=stereo"]
    if usable:
        cmd += ["-loop", "1", "-framerate", "30000/1001", "-i", usable]
        filter_complex = (
            "[2:v]scale=60:60:force_original_aspect_ratio=decrease,setsar=1[logo];"
            "[0:v][logo]overlay=x=(W-w)/2:y=(H-h)/2[v]"
        )
        cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    else:
        cmd += ["-map", "0:v"]
    cmd += [
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-c:a", "ac3",
        "-metadata:s:a:0", f"title={channel_name}",
        "-metadata:s:a:0", f"language={_lang_code(channel_name)}",
        "-f", "mpegts", "pipe:1",
    ]

    proc = _Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            chunk = proc.stdout.read(32768)
            if not chunk:
                break
            yield chunk
            if proxy_server.get_buffer(channel_id) is not None:
                break
    finally:
        _kill_proc(proc)


def _build_placeholder_cmd(
    channel_names: list[str],
    logo_urls: list[str | None],
    layout: str,
    out_w: int,
    out_h: int,
    audio_source: str = "0",
) -> list[str]:
    n = len(channel_names)

    if layout == "featured":
        main_w, main_h, side_w, side_h, positions = _layouts._featured_layout(n, out_w, out_h)
        tile_sizes = [(main_w, main_h)] + [(side_w, side_h)] * (n - 1)
    elif layout == "top_featured":
        main_w, main_h, tile_w, bottom_h, positions = _layouts._top_featured_layout(n, out_w, out_h)
        tile_sizes = [(main_w, main_h)] + [(tile_w, bottom_h)] * (n - 1)
    else:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        tile_w = out_w // cols
        tile_h = out_h // rows
        tile_sizes = [(tile_w, tile_h)] * n
        positions = _layouts._centered_grid_positions(n, cols, rows, tile_w, tile_h)

    # Determine which tiles have usable local logos
    usable = [_usable_logo(u) for u in logo_urls]

    # Determine which tiles have usable local logos
    usable = [_usable_logo(u) for u in logo_urls]

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning"]
    for tw, th in tile_sizes:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:size={tw}x{th}:r=30000/1001"]
    audio_count = n if audio_source == "all" else 1
    for _ in range(audio_count):
        cmd += ["-f", "lavfi", "-i", "aevalsrc=0:sample_rate=48000:channel_layout=stereo"]

    # Add logo file inputs and track their indices.
    # -loop 1 makes ffmpeg loop the still image for the full -t duration;
    # without it the image is a single-frame stream and the overlay pipeline
    # terminates after ~1 frame.
    logo_input_idx: dict[int, int] = {}
    next_idx = n + audio_count
    for i, logo_path in enumerate(usable):
        if logo_path:
            cmd += ["-loop", "1", "-framerate", "30000/1001", "-i", logo_path]
            logo_input_idx[i] = next_idx
            next_idx += 1

    # Add logo file inputs and track their indices.
    # -loop 1 makes ffmpeg loop the still image for the full -t duration;
    # without it the image is a single-frame stream and the overlay pipeline
    # terminates after ~1 frame.
    logo_input_idx: dict[int, int] = {}
    next_idx = n + audio_count
    for i, logo_path in enumerate(usable):
        if logo_path:
            cmd += ["-loop", "1", "-framerate", "30000/1001", "-i", logo_path]
            logo_input_idx[i] = next_idx
            next_idx += 1

    filter_parts = []
    for i, (tw, th) in enumerate(tile_sizes):
        logo_idx = logo_input_idx.get(i)
        if logo_idx is not None:
            logo_size = min(tw, th) // 3
            filter_parts.append(
                f"[{logo_idx}:v]scale={logo_size}:{logo_size}"
                f":force_original_aspect_ratio=decrease,setsar=1[ls{i}];"
                f"[{i}:v][ls{i}]overlay=x=(W-w)/2:y=(H-h)/2[t{i}]"
            )
        else:
            filter_parts.append(f"[{i}:v]copy[t{i}]")

    inputs_str = "".join(f"[t{i}]" for i in range(n))
    xstack = f"{inputs_str}xstack=inputs={n}:layout={'|'.join(positions)}:fill=black[v]"
    font_size = max(24, out_h // 30)
    filter_complex = (
        "; ".join(filter_parts) + "; " + xstack
        + f"; [v]drawtext=text='Starting up...':fontcolor=white:fontsize={font_size}"
          f":x=(w-text_w)/2:y=h-th-20:box=1:boxcolor=black@0.7:boxborderw=8[vo]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vo]",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
    ]

    if audio_source == "all":
        for i in range(n):
            cmd += ["-map", f"{n + i}:a"]
        cmd += ["-c:a", "ac3"]
    else:
        audio_idx = int(audio_source) if str(audio_source).isdigit() else 0
        audio_idx = max(0, min(audio_idx, n - 1))
        cmd += ["-map", f"{n}:a", "-c:a", "ac3"]
    cmd += _audio_metadata_args(audio_source, channel_names, n)

    cmd += [
        "-t", str(max(5, n * 4)),
        "-mpegts_flags", "+pat_pmt_at_frames+resend_headers+initial_discontinuity",
        "-f", "mpegts", "pipe:1",
    ]
    return cmd


def _build_ffmpeg_cmd(
    input_urls: list[str],
    layout: str,
    settings: dict,
    audio_source: str = "0",
    channel_names: list[str] | None = None,
) -> list[str]:
    n = len(input_urls)

    out_w, out_h = _parse_resolution(settings)
    bitrate      = int(settings.get("output_bitrate") or 8000)
    crf          = int(settings.get("output_crf") or 23)
    preset       = settings.get("encoder_preset") or "ultrafast"
    encoder      = settings.get("video_encoder") or "libx264"
    vaapi_device = settings.get("vaapi_device") or "/dev/dri/renderD128"

    if encoder == "h264_vaapi":
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning",
               "-vaapi_device", vaapi_device]
    else:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning"]

    for url in input_urls:
        cmd += [
            "-f", "mpegts",
            "-fflags", "+discardcorrupt+genpts+nobuffer",
            "-analyzeduration", "1000000",
            "-probesize", "1048576",
            "-thread_queue_size", "1024",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", url,
        ]

    if layout == "featured":
        filter_complex, map_args = _layouts._featured_filter(n, out_w, out_h)
    elif layout == "top_featured":
        filter_complex, map_args = _layouts._top_featured_filter(n, out_w, out_h)
    else:
        filter_complex, map_args = _layouts._auto_grid_filter(n, out_w, out_h)

    if encoder == "h264_vaapi":
        filter_complex = filter_complex.replace("[v]", "[vraw]", 1)
        filter_complex += "; [vraw]hwupload,format=vaapi[v]"

    cmd += ["-filter_complex", filter_complex]
    cmd += map_args

    _NVENC_VALID_PRESETS = {"p1", "p2", "p3", "p4", "p5", "p6", "p7"}
    if encoder == "h264_nvenc":
        nvenc_preset = preset if preset in _NVENC_VALID_PRESETS else "p1"
        cmd += [
            "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-tune", "ll",
            "-rc", "vbr",
            "-cq", str(crf),
            "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate * 2}k",
            "-g", "60", "-keyint_min", "60",
        ]
    elif encoder == "h264_qsv":
        _qsv_valid = {"veryfast", "faster", "fast", "medium", "slow"}
        qsv_preset = preset if preset in _qsv_valid else "veryfast"
        cmd += [
            "-c:v", "h264_qsv",
            "-preset", qsv_preset,
            "-global_quality", str(crf),
            "-b:v", f"{bitrate}k",
            "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate * 2}k",
            "-g", "60", "-low_power", "1",
        ]
    elif encoder == "h264_vaapi":
        cmd += [
            "-c:v", "h264_vaapi",
            "-b:v", f"{bitrate}k",
            "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate * 2}k",
            "-g", "60",
        ]
    else:  # libx264
        cmd += [
            "-c:v", "libx264",
            "-preset", preset,
            "-tune", "zerolatency",
            "-level:v", "5.1",
            "-crf", str(crf),
            "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate * 2}k",
            "-g", "60", "-keyint_min", "60",
            "-sc_threshold", "0",
            "-force_key_frames", "expr:gte(t,n_forced*2)",
        ]

    if audio_source == "all":
        for i in range(n):
            cmd += ["-map", f"{i}:a?"]
        cmd += ["-c:a", "ac3"]
    else:
        audio_idx = int(audio_source) if str(audio_source).isdigit() else 0
        audio_idx = max(0, min(audio_idx, n - 1))
        cmd += ["-map", f"{audio_idx}:a", "-c:a", "ac3"]
    cmd += _audio_metadata_args(audio_source, channel_names or [], n)

    cmd += ["-max_muxing_queue_size", "1024"]
    cmd += ["-mpegts_flags", "+pat_pmt_at_frames+resend_headers+initial_discontinuity"]
    cmd += ["-f", "mpegts", "pipe:1"]
    return cmd


# Server

class MultiviewServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._server = None
        self._greenlet = None
        self.running = False

    # WSGI

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

        if path.startswith("/internal/ch/"):
            channel_id = path[len("/internal/ch/"):]
            return self._serve_channel_internal(channel_id, start_response)

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    def _serve_stream(self, n: int, start_response):
        logger.info(f"Stream request: layout {n}")
        try:
            input_urls, layout, channel_names, logo_urls, audio_source = self._resolve_layout(n)
        except LookupError as e:
            logger.warning(f"Layout {n} not ready: {e}")
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [str(e).encode()]
        except Exception as e:
            logger.error(f"Error resolving layout {n}: {e}", exc_info=True)
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Server error\n"]

        try:
            from apps.plugins.models import PluginConfig
            cfg = PluginConfig.objects.get(key="multiview")
            enc_settings = cfg.settings
        except Exception:
            enc_settings = {}

        resolution = enc_settings.get("output_resolution", "1920x1080")
        out_w, out_h = _parse_resolution(enc_settings)

        try:
            import gevent as _gevent
            import gevent.queue as _gqueue
            import gevent.event as _gevent_event
            import gevent.subprocess as _gsp
            _Popen = _gsp.Popen
            _has_gevent = True
        except ImportError:
            _Popen = subprocess.Popen
            _has_gevent = False

        placeholder_cmd = _build_placeholder_cmd(channel_names, logo_urls, layout, out_w, out_h, audio_source)
        real_cmd = _build_ffmpeg_cmd(input_urls, layout, enc_settings, audio_source, channel_names)

        logger.info(
            f"Starting placeholder + real ffmpeg: layout={n} inputs={len(input_urls)} "
            f"style={layout} encoder={enc_settings.get('video_encoder', 'libx264')} "
            f"resolution={resolution}"
        )

        logger.debug(f"placeholder_cmd: {placeholder_cmd}")
        logger.debug(f"real_cmd: {real_cmd}")
        placeholder_proc = _Popen(placeholder_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        real_proc = _Popen(real_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        threading.Thread(
            target=_log_stderr, args=(real_proc, f"layout={n}"),
            daemon=True, name=f"ffmpeg-stderr-{n}",
        ).start()

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("Transfer-Encoding", "chunked"),
        ])

        if _has_gevent:
            # placeholder_q: placeholder chunks (small buffer, so we don't over-fill)
            # real_first_q: the first chunk from real ffmpeg (signals it's alive)
            placeholder_q    = _gqueue.Queue(maxsize=1)
            real_first_q     = _gqueue.Queue(maxsize=1)
            real_ready       = _gevent_event.Event()
            placeholder_done = _gevent_event.Event()

            def _read_placeholder():
                try:
                    while not real_ready.is_set():
                        chunk = placeholder_proc.stdout.read(32768)
                        if not chunk:
                            break
                        if real_ready.is_set():
                            break
                        try:
                            placeholder_q.put(chunk, timeout=1)
                        except Exception:
                            break
                finally:
                    placeholder_done.set()
                    _kill_proc(placeholder_proc)

            def _probe_real():
                first = real_proc.stdout.read(65536)
                real_first_q.put(first if first else b"")
                real_ready.set()

            _gevent.spawn(_read_placeholder)
            _gevent.spawn(_probe_real)

            def stream_gen():
                bytes_sent = 0
                try:
                    # Phase 1: placeholder until it ends (-t 10) OR real is ready
                    while not placeholder_done.is_set() and not real_ready.is_set():
                        try:
                            chunk = placeholder_q.get(timeout=0.1)
                            bytes_sent += len(chunk)
                            yield chunk
                        except _gqueue.Empty:
                            continue

                    # Phase 2: null-packet keepalive until real ffmpeg is ready.
                    # Null packets (PID 0x1FFF) are transparent; decoders discard
                    # them without filling the client's visible buffer.
                    while not real_ready.is_set():
                        yield _NULL_TS_BURST
                        bytes_sent += len(_NULL_TS_BURST)
                        _gevent.sleep(0.25)

                    # Phase 3: hand off first real chunk
                    try:
                        first = real_first_q.get(timeout=3)
                    except _gqueue.Empty:
                        first = b""
                    if not first:
                        return
                    bytes_sent += len(first)
                    yield first

                    # Phase 4: stream real ffmpeg
                    while True:
                        chunk = real_proc.stdout.read(65536)
                        if not chunk:
                            break
                        bytes_sent += len(chunk)
                        yield chunk
                finally:
                    for proc in (real_proc, placeholder_proc):
                        _kill_proc(proc)
                    logger.info(f"ffmpeg layout={n} terminated after {bytes_sent:,} bytes")

        else:
            def stream_gen():
                bytes_sent = 0
                try:
                    for proc in (placeholder_proc, real_proc):
                        while True:
                            chunk = proc.stdout.read(65536)
                            if not chunk:
                                break
                            bytes_sent += len(chunk)
                            yield chunk
                finally:
                    for proc in (placeholder_proc, real_proc):
                        _kill_proc(proc)
                    logger.info(f"ffmpeg layout={n} terminated after {bytes_sent:,} bytes")

        return stream_gen()

    def _ensure_channel_initialized(self, channel_id: str) -> bool:
        """Initialize a channel via ProxyServer and wait for its buffer. Returns True if started fresh."""
        try:
            from django.db import close_old_connections
            close_old_connections()
        except Exception:
            pass

        try:
            from apps.proxy.live_proxy.server import ProxyServer
            from apps.proxy.live_proxy.services.channel_service import ChannelService
            from apps.proxy.live_proxy.url_utils import generate_stream_url
            from apps.channels.models import Channel
        except ImportError as e:
            logger.error(f"Import error in _ensure_channel_initialized: {e}")
            return False

        try:
            proxy_server = ProxyServer.get_instance()
        except Exception as e:
            logger.error(f"Could not get ProxyServer instance: {e}")
            return False

        if not proxy_server.check_if_channel_exists(channel_id):
            stream_url, stream_ua, transcode, profile_value = generate_stream_url(channel_id)
            if not stream_url:
                logger.warning(f"No stream available for channel {channel_id}")
                return False

            stream_id = m3u_profile_id = None
            if proxy_server.redis_client:
                try:
                    ch = Channel.objects.get(uuid=channel_id)
                    raw = proxy_server.redis_client.get(f"channel_stream:{ch.id}")
                    if raw:
                        stream_id = int(raw)
                        raw2 = proxy_server.redis_client.get(f"stream_profile:{stream_id}")
                        if raw2:
                            m3u_profile_id = int(raw2)
                except Exception as e:
                    logger.warning(f"Could not read stream assignment from Redis: {e}")

            success = ChannelService.initialize_channel(
                channel_id, stream_url, stream_ua, transcode,
                profile_value, stream_id, m3u_profile_id,
            )
            if not success:
                logger.error(f"Failed to initialize channel {channel_id}")
                return False

            _sleep = _gevent_sleep()

            for _ in range(30):
                if proxy_server.get_buffer(channel_id) is not None:
                    break
                _sleep(0.2)

            for _ in range(15):
                if channel_id in proxy_server.client_managers:
                    break
                _sleep(0.2)

            return True
        else:
            logger.info(f"Channel {channel_id} already running, attaching directly")
            return False

    def _serve_channel_internal(self, channel_id: str, start_response):
        """Internal endpoint consumed by ffmpeg. Opens the channel through ProxyServer."""
        try:
            _uuid_module.UUID(channel_id)
        except ValueError:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"Invalid channel UUID\n"]

        logger.info(f"Internal channel request: {channel_id}")

        try:
            from apps.proxy.live_proxy.server import ProxyServer
            from apps.proxy.live_proxy.output.ts.generator import StreamGenerator
        except ImportError as e:
            logger.error(f"Import error in _serve_channel_internal: {e}")
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Server error\n"]

        try:
            proxy_server = ProxyServer.get_instance()
        except Exception as e:
            logger.error(f"Could not get ProxyServer instance: {e}")
            start_response("503 Service Unavailable", [("Content-Type", "text/plain")])
            return [b"Proxy server unavailable\n"]

        # Look up channel metadata for placeholder
        channel_name = channel_id
        logo_url = None
        try:
            from apps.channels.models import Channel
            ch_obj = Channel.objects.select_related("logo").get(uuid=channel_id)
            channel_name = ch_obj.name
            logo_url = ch_obj.logo.url if ch_obj.logo_id is not None else None
        except Exception:
            pass

        try:
            self._ensure_channel_initialized(channel_id)
        except Exception as e:
            logger.warning(f"Channel init warning {channel_id}: {e}")
            # Don't 503; serve placeholder and wait for channel to become available

        client_id = str(_uuid_module.uuid4())

        start_response("200 OK", [
            ("Content-Type", "video/mp2t"),
            ("Cache-Control", "no-cache"),
            ("Transfer-Encoding", "chunked"),
        ])

        _sleep = _gevent_sleep()

        def stream_gen():
            _active_client = False
            try:
                while True:
                    buf = proxy_server.get_buffer(channel_id)

                    if buf is None:
                        if _active_client:
                            try:
                                mgr = proxy_server.client_managers.get(channel_id)
                                if mgr:
                                    mgr.remove_client(client_id)
                            except Exception:
                                pass
                            _active_client = False
                        logger.info(f"Channel {channel_id} buffer gone, serving placeholder")
                        yield from _single_channel_placeholder_gen(
                            channel_id, channel_name, logo_url, proxy_server
                        )
                        logger.info(f"Channel {channel_id} buffer returned, resuming")
                        continue

                    if not _active_client:
                        mgr = proxy_server.client_managers.get(channel_id)
                        if mgr is None:
                            _sleep(0.5)
                            continue
                        try:
                            mgr.add_client(
                                client_id, "127.0.0.1", "multiview-plugin", None, "mpegts", None,
                            )
                            _active_client = True
                            logger.info(f"Registered client {client_id} for {channel_id}")
                        except Exception as e:
                            logger.warning(f"add_client failed for {channel_id}: {e}")
                            _sleep(0.5)
                            continue

                    gen = StreamGenerator(
                        channel_id=channel_id,
                        client_id=client_id,
                        client_ip="127.0.0.1",
                        client_user_agent="multiview-plugin",
                        channel_initializing=False,
                        buffer=buf,
                    )
                    try:
                        yield from gen.generate()
                    except GeneratorExit:
                        return
                    except Exception as e:
                        logger.warning(f"StreamGenerator error for {channel_id}: {e}")
                    # StreamGenerator._cleanup() removed our client
                    _active_client = False
                    logger.info(f"StreamGenerator restarting for {channel_id}")
                    _sleep(0.05)
            finally:
                if _active_client:
                    try:
                        mgr = proxy_server.client_managers.get(channel_id)
                        if mgr is not None:
                            mgr.remove_client(client_id)
                            logger.info(f"Removed client {client_id} from {channel_id}")
                    except Exception:
                        pass

        return stream_gen()

    def _resolve_layout(self, n: int) -> tuple[list[str], str, list[str], list[str | None], str]:
        """Return ([internal_channel_urls], layout_name, [channel_names], [logo_urls]) for layout n."""
        from apps.plugins.models import PluginConfig
        from apps.channels.models import Channel

        try:
            cfg = PluginConfig.objects.get(key="multiview")
            settings = cfg.settings
        except Exception:
            settings = {}

        ch_count = max(2, int(settings.get(f"multiview_{n}_channel_count", 4)))
        layout = settings.get(f"multiview_{n}_layout", "auto")
        selector_type = settings.get(f"multiview_{n}_selector_type", "classic")

        logger.info(f"Resolving layout {n}: ch_count={ch_count} style={layout} selector={selector_type}")
        input_urls = []
        channel_names = []
        logo_urls = []

        if selector_type == "regex":
            pattern = settings.get(f"multiview_{n}_regex_pattern", "").strip()
            if not pattern:
                raise LookupError(f"Layout {n} is in regex mode but has no pattern configured")
            matched = list(
                Channel.objects.select_related("logo")
                .filter(name__iregex=pattern)
                .order_by("channel_number")[:ch_count]
            )
            for ch in matched:
                url = f"http://127.0.0.1:{self.port}/internal/ch/{ch.uuid}"
                logger.info(f"  regex match: name={ch.name!r} url={url}")
                input_urls.append(url)
                channel_names.append(ch.name)
                try:
                    logo_urls.append(ch.logo.url if ch.logo_id is not None else None)
                except Exception:
                    logo_urls.append(None)
            audio_source = settings.get(f"multiview_{n}_audio_source", "regex_first")
            if audio_source in ("regex_first", "regex_lowest"):
                audio_source = "0"  # both map to index 0 of the channel_number-sorted list
        else:
            for m in range(1, ch_count + 1):
                ch_id_str = settings.get(f"multiview_{n}_channel_{m}", "_none")
                if not ch_id_str or ch_id_str == "_none":
                    logger.info(f"  channel {m}: skipped (not configured)")
                    continue
                try:
                    ch = Channel.objects.select_related("logo").get(id=int(ch_id_str))
                except Channel.DoesNotExist:
                    logger.warning(f"  channel {m}: id={ch_id_str} not found, skipping")
                    continue
                url = f"http://127.0.0.1:{self.port}/internal/ch/{ch.uuid}"
                logger.info(f"  channel {m}: id={ch_id_str} name={ch.name!r} url={url}")
                input_urls.append(url)
                channel_names.append(ch.name)
                try:
                    logo_urls.append(ch.logo.url if ch.logo_id is not None else None)
                except Exception:
                    logo_urls.append(None)
            audio_source = settings.get(f"multiview_{n}_audio_source", "0")

        if len(input_urls) < 2:
            raise LookupError(
                f"Layout {n} needs at least 2 configured channels (found {len(input_urls)})"
            )

        return input_urls, layout, channel_names, logo_urls, audio_source

    # Lifecycle

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

            def _run():
                try:
                    self._server = pywsgi.WSGIServer(
                        (self.host, self.port),
                        self.wsgi_app,
                        log=None,
                    )
                    self.running = True
                    set_server(self)
                    self._server.serve_forever()
                except Exception as e:
                    logger.error(f"Multiview server crashed: {e}", exc_info=True)
                finally:
                    self.running = False

            import gevent as _gevent
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
