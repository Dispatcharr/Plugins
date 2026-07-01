"""Channel decoder: one child IPTV stream demuxed into video and audio buffers.

Imported by compositor_worker.py (the subprocess entry point). Lives here so
the PyAV/numpy dependency and the YUV compositing utilities are co-located with
the class that uses them, separate from the encoder and orchestration code.
"""

import os
import platform
import sys
import threading
import time

# Vendored PyAV is shipped per-platform under vendor/<os-arch>/; pick the one
# matching this machine and put it on the path before importing av.
_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
_ARCH_DIR = {
    "x86_64": "linux-x86_64", "amd64": "linux-x86_64",
    "aarch64": "linux-aarch64", "arm64": "linux-aarch64",
}.get(platform.machine().lower())
if _ARCH_DIR and os.path.isdir(os.path.join(_VENDOR, _ARCH_DIR)):
    sys.path.insert(0, os.path.join(_VENDOR, _ARCH_DIR))

import numpy as np  # noqa: E402
try:
    import av  # noqa: E402  (vendored, installed on demand)
except ImportError:
    sys.stderr.write(
        f"[mvworker] FATAL: PyAV not installed for arch '{platform.machine()}' "
        f"(expected {_VENDOR}/{_ARCH_DIR}). Open the Multiview plugin settings and "
        f"run the 'Install PyAV' action.\n")
    raise

TILE_STALE_SECS = 1.5
RECONNECT_BASE    = 2.0   # first retry delay (seconds)
RECONNECT_MAX     = 60.0  # cap on per-retry delay
RECONNECT_RETRIES = 12    # consecutive failures before giving up (~8 min total)
AUDIO_RATE = 48000
AUDIO_LAYOUT = "stereo"

# Tolerate flaky IPTV (skip corrupt packets, ignore decode errors, generous
# probe) and bound I/O so a dead child errors and retries instead of hanging.
# Matches what the old ffmpeg tile decoders used; PyAV's strict defaults choke
# on partial/corrupt mpegts ("Invalid data found when processing input").
DECODE_OPTS = {
    "fflags": "+discardcorrupt+genpts",
    "analyzeduration": "5000000",
    "probesize": "5000000",
    "err_detect": "ignore_err",
    "rw_timeout": "15000000",   # 15s I/O timeout (microseconds)
}


def log(msg):
    sys.stderr.write(f"[mvworker] {msg}\n")
    sys.stderr.flush()


def yuv_planes_from_frame(frame, w, h):
    """Extract (Y, U, V) as contiguous numpy arrays from a yuv420p VideoFrame,
    stripping each plane's stride padding."""
    p0, p1, p2 = frame.planes
    Y = np.frombuffer(memoryview(p0), np.uint8).reshape(h, p0.line_size)[:, :w]
    U = np.frombuffer(memoryview(p1), np.uint8).reshape(h // 2, p1.line_size)[:, :w // 2]
    V = np.frombuffer(memoryview(p2), np.uint8).reshape(h // 2, p2.line_size)[:, :w // 2]
    return Y.copy(), U.copy(), V.copy()


def black_planes(w, h):
    return (np.zeros((h, w), np.uint8),
            np.full((h // 2, w // 2), 128, np.uint8),
            np.full((h // 2, w // 2), 128, np.uint8))


def _yuv_planes(buf, w, h):
    """(Y, U, V) plane views into a flat yuv420p buffer (Y|U|V byte order)."""
    ysize = w * h
    csize = (w // 2) * (h // 2)
    Y = buf[:ysize].reshape(h, w)
    U = buf[ysize:ysize + csize].reshape(h // 2, w // 2)
    V = buf[ysize + csize:ysize + 2 * csize].reshape(h // 2, w // 2)
    return Y, U, V


def _even(v):
    return max(2, (int(v) // 2) * 2)


def fit_into_tile(frame, w, h, valign="center", halign="center"):
    """Scale a decoded frame into a w x h yuv420p tile, preserving aspect
    ratio (content is never cropped). Letterbox/pillarbox padding is
    centered by default, or pushed to one edge via valign ("center"/"top"/
    "bottom") and halign ("center"/"left"/"right") so a tile's content can
    be made to touch an adjacent tile's content with no gap at the shared
    edge, leaving any padding on the outer edge instead."""
    sw, sh = frame.width, frame.height
    if sw <= 0 or sh <= 0:
        return black_planes(w, h)
    scale = min(w / sw, h / sh)
    tw, th = _even(sw * scale), _even(sh * scale)
    tw, th = min(tw, w), min(th, h)
    sf = frame.reformat(width=tw, height=th, format="yuv420p")
    sy, su, sv = yuv_planes_from_frame(sf, tw, th)
    Y, U, V = black_planes(w, h)
    if halign == "left":
        ox = 0
    elif halign == "right":
        ox = (w - tw) & ~1
    else:
        ox = ((w - tw) // 2) & ~1
    if valign == "top":
        oy = 0
    elif valign == "bottom":
        oy = (h - th) & ~1
    else:
        oy = ((h - th) // 2) & ~1
    Y[oy:oy + th, ox:ox + tw] = sy
    U[oy // 2:oy // 2 + th // 2, ox // 2:ox // 2 + tw // 2] = su
    V[oy // 2:oy // 2 + th // 2, ox // 2:ox // 2 + tw // 2] = sv
    return (Y, U, V)


class Channel:
    """One child channel: ONE realsrc connection, demuxed into this tile's video
    and (if this channel supplies audio) its audio track. Decoding each channel
    once (instead of separate video+audio connections) halves the load on the
    provider/proxy, which was corrupting the video under multiview load."""

    def __init__(self, spec):
        self.url = spec["url"]
        self.x, self.y = spec["x"], spec["y"]
        self.w, self.h = spec["w"], spec["h"]
        self.name = spec.get("name", "")
        self.provides_audio = bool(spec.get("audio", False))
        self.lang = spec.get("lang", "und")
        self.featured = bool(spec.get("featured", False))
        self.valign = spec.get("valign", "center")
        self.halign = spec.get("halign", "center")
        self.fallback = black_planes(self.w, self.h)
        self.latest = self.fallback
        self.fresh_until = 0.0
        logo = spec.get("logo")
        if logo:
            threading.Thread(target=self._load_logo, args=(logo,), daemon=True).start()
        self.running = True
        self.vcount = 0          # decoded video frames (for rate diagnostics)
        # audio buffer (only used when provides_audio)
        self.alock = threading.Lock()
        self.aframes = []        # list of (pts_s: float|None, ndarray(n,2) int16)
        self.abuffered = 0
        # video PTS clock anchor — updated by run(), read by audio_pts_now()
        self.clk_pts: "float | None" = None
        self.clk_wall: "float | None" = None
        # PTS of the audio content most recently handed to the caller by take() —
        # used by audio_feeder() to detect drift against the video clock and
        # periodically re-sync via _align_to_pts(), without waiting for a full
        # clk_pts reset. Protected by self.alock (same as aframes/abuffered).
        self.last_taken_pts: "float | None" = None
        self._reconnect_requested = False

    def _make_fallback(self, logo):
        Y, U, V = black_planes(self.w, self.h)
        if logo:
            try:
                with av.open(logo) as c:
                    for frame in c.decode(video=0):
                        # Scale to fit within one-third of the tile, preserving aspect ratio.
                        max_w = (self.w // 3) & ~1
                        max_h = (self.h // 3) & ~1
                        scale = min(max_w / frame.width, max_h / frame.height)
                        lw = _even(frame.width * scale)
                        lh = _even(frame.height * scale)
                        # Decode as RGBA so transparent areas composite cleanly over black.
                        # Use to_ndarray() -- planes[0] has stride padding that makes
                        # raw frombuffer shapes wrong for non-aligned widths.
                        rf = frame.reformat(width=lw, height=lh, format="rgba")
                        arr = rf.to_ndarray(format="rgba")   # (lh, lw, 4), stride-free
                        alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
                        rgb = (arr[:, :, :3] * alpha).astype(np.uint8)
                        rgb_frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
                        lf = rgb_frame.reformat(format="yuv420p")
                        ly, lu, lv = yuv_planes_from_frame(lf, lw, lh)
                        oy = ((self.h - lh) // 2) & ~1
                        ox = ((self.w - lw) // 2) & ~1
                        Y[oy:oy + lh, ox:ox + lw] = ly
                        U[oy // 2:(oy + lh) // 2, ox // 2:(ox + lw) // 2] = lu
                        V[oy // 2:(oy + lh) // 2, ox // 2:(ox + lw) // 2] = lv
                        break
            except Exception as e:  # noqa: BLE001
                log(f"logo decode failed for {self.name}: {e}")
        return (Y, U, V)

    def _load_logo(self, logo):
        """Load logo in background and swap self.fallback when ready."""
        fb = self._make_fallback(logo)
        self.fallback = fb                  # CPython GIL makes tuple attr swap atomic
        if self.fresh_until == 0.0:         # no real video yet; update latest too
            self.latest = fb

    def reconnect(self):
        """Signal run() to drop and reconnect; checked inside the demux loop."""
        self._reconnect_requested = True

    def run(self):
        failures = 0
        while self.running:
            if self._reconnect_requested:
                self._reconnect_requested = False
                failures = 0
            if failures >= RECONNECT_RETRIES:
                log(f"channel {self.name}: giving up after {RECONNECT_RETRIES} failed retries")
                break
            cont = None
            # Flush stale audio and reset the PTS clock before each new
            # connection so old samples never bleed into the new stream.
            with self.alock:
                self.aframes.clear()
                self.abuffered = 0
                self.last_taken_pts = None
            self.clk_pts = None
            self.clk_wall = None
            vcount_before = self.vcount
            try:
                cont = av.open(self.url, options=DECODE_OPTS)
                vs = cont.streams.video[0]
                # Multi-threaded decode so 1080p sources keep up with the output
                # rate (single-threaded PyAV decode runs ~22-27fps -> slow motion).
                vs.thread_type = "AUTO"
                vs.codec_context.thread_count = 3
                # Sources are 1080p60 but we output 30fps; skip non-reference
                # (B) frames at decode to cut decode CPU on the box, which
                # otherwise saturates (3x 1080p60 decode + encode).
                try:
                    vs.codec_context.skip_frame = "NONREF"
                except Exception:
                    pass
                # Lower-effort decode for non-featured tiles: skip the deblocking
                # loop filter. Big decode-CPU saving; the minor blockiness is
                # hidden by downscaling small tiles. The featured tile keeps full
                # deblocking so it stays sharp.
                if not self.featured:
                    try:
                        vs.codec_context.skip_loop_filter = "ALL"
                    except Exception:
                        pass
                streams = [vs]
                res = None
                aus = None
                if self.provides_audio and cont.streams.audio:
                    aus = cont.streams.audio[0]
                    streams.append(aus)
                    res = av.AudioResampler(format="s16", layout=AUDIO_LAYOUT, rate=AUDIO_RATE)
                try:
                    for packet in cont.demux(*streams):
                        if not self.running or self._reconnect_requested:
                            break
                        if packet.dts is None:
                            continue
                        if packet.stream.type == "video":
                            for frame in packet.decode():
                                if frame.pts is not None:
                                    pts_s = float(frame.pts * vs.time_base)
                                    now = time.monotonic()
                                    if self.clk_pts is None:
                                        self.clk_pts, self.clk_wall = pts_s, now
                                    else:
                                        gap = (self.clk_wall + pts_s - self.clk_pts) - now
                                        if 0 < gap < 2.0:
                                            time.sleep(gap)
                                        elif gap <= -2.0:
                                            self.clk_pts, self.clk_wall = pts_s, time.monotonic()
                                self.latest = fit_into_tile(frame, self.w, self.h, self.valign, self.halign)
                                self.fresh_until = time.monotonic() + TILE_STALE_SECS
                                self.vcount += 1
                        elif res is not None and packet.stream.type == "audio":
                            for frame in packet.decode():
                                pts_s = (float(frame.pts * aus.time_base)
                                         if frame.pts is not None else None)
                                for rf in res.resample(frame):
                                    a = rf.to_ndarray()
                                    a = a.reshape(-1, 2) if a.shape[0] == 1 else a.T
                                    with self.alock:
                                        self.aframes.append((pts_s, a.astype(np.int16)))
                                        self.abuffered += a.shape[0]
                                        self._trim()
                finally:
                    if res is not None:
                        try:
                            res.close()
                        except Exception:
                            pass
            except Exception as e:  # noqa: BLE001
                log(f"channel {self.name} ended: {e}")
            finally:
                if cont is not None:
                    try:
                        cont.close()
                    except Exception:
                        pass
            if self.vcount > vcount_before:
                failures = 0
            else:
                failures += 1
            if self.running and failures < RECONNECT_RETRIES:
                delay = min(RECONNECT_BASE * (2 ** (failures - 1)), RECONNECT_MAX)
                log(f"channel {self.name}: retry {failures}/{RECONNECT_RETRIES} in {delay:.0f}s")
                time.sleep(delay)

    def current(self):
        if time.monotonic() < self.fresh_until:
            return self.latest
        return self.fallback

    def _trim(self):
        cap = AUDIO_RATE * 2  # ~2s
        while self.abuffered > cap and self.aframes:
            _, drop = self.aframes.pop(0)
            self.abuffered -= drop.shape[0]

    def audio_pts_now(self) -> "float | None":
        """Current source PTS (seconds) implied by the video clock anchor."""
        if self.clk_pts is None or self.clk_wall is None:
            return None
        return self.clk_pts + (time.monotonic() - self.clk_wall)

    def _align_to_pts(self, pts_limit: float):
        """Discard buffered audio chunks that end before pts_limit."""
        with self.alock:
            while self.aframes:
                pts_s, chunk = self.aframes[0]
                if pts_s is None:
                    break
                if pts_s + chunk.shape[0] / AUDIO_RATE < pts_limit:
                    self.aframes.pop(0)
                    self.abuffered -= chunk.shape[0]
                else:
                    break

    def take(self, nsamples: int) -> np.ndarray:
        """Return exactly nsamples of int16 (nsamples, 2), silence-padded."""
        out = np.zeros((nsamples, 2), np.int16)
        filled = 0
        with self.alock:
            while filled < nsamples and self.aframes:
                pts_s, chunk = self.aframes[0]
                need = nsamples - filled
                if chunk.shape[0] <= need:
                    out[filled:filled + chunk.shape[0]] = chunk
                    self.aframes.pop(0)
                    self.abuffered -= chunk.shape[0]
                    filled += chunk.shape[0]
                    if pts_s is not None:
                        self.last_taken_pts = pts_s + chunk.shape[0] / AUDIO_RATE
                else:
                    out[filled:] = chunk[:need]
                    self.aframes[0] = (pts_s, chunk[need:])
                    self.abuffered -= need
                    filled = nsamples
                    if pts_s is not None:
                        self.last_taken_pts = pts_s + need / AUDIO_RATE
        return out
