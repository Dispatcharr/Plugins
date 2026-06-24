"""Multiview compositor worker (separate process, no gevent).

Spawned by server._serve_stream as `python compositor_worker.py <config-json>`. It
runs as a plain CPython process (so real threads parallelize across cores and
nothing fights Dispatcharr's gevent hub), using vendored PyAV to:

  * decode each child channel in its own thread, keeping that tile's latest frame
    (or a logo/black fallback card when the child is stale/down),
  * composite a numpy canvas at the target fps (latest-frame, so a slow/dead child
    never stalls the grid: no synchronous barrier),
  * decode + resample each selected channel's audio into per-track buffers,
  * encode one libx264 video stream + N ac3 audio tracks to MPEG-TS on stdout.

The plugin's gevent server just reads this process's stdout and forwards it to
Dispatcharr (the proven low-volume boundary). Config schema (argv[1] JSON):

  {"out_w","out_h","fps","bitrate","crf","preset",
   "tiles":[{"url","x","y","w","h","logo","name"}...],
   "audio":[{"url","name","lang"}...]}
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
from fractions import Fraction

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
RECONNECT_BACKOFF = 2.0
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


def fps_fraction(fps: str) -> Fraction:
    if "/" in fps:
        a, b = fps.split("/")
        return Fraction(int(a), int(b))
    return Fraction(int(fps), 1)


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


def fit_into_tile(frame, w, h):
    """Scale a decoded frame into a w x h yuv420p tile preserving aspect ratio,
    centered on black (letterbox/pillarbox) - matches the old scale+pad behavior."""
    sw, sh = frame.width, frame.height
    if sw <= 0 or sh <= 0:
        return black_planes(w, h)
    scale = min(w / sw, h / sh)
    tw, th = _even(sw * scale), _even(sh * scale)
    tw, th = min(tw, w), min(th, h)
    sf = frame.reformat(width=tw, height=th, format="yuv420p")
    sy, su, sv = yuv_planes_from_frame(sf, tw, th)
    Y, U, V = black_planes(w, h)
    ox = ((w - tw) // 2) & ~1
    oy = ((h - th) // 2) & ~1
    Y[oy:oy + th, ox:ox + tw] = sy
    U[oy // 2:oy // 2 + th // 2, ox // 2:ox // 2 + tw // 2] = su
    V[oy // 2:oy // 2 + th // 2, ox // 2:ox // 2 + tw // 2] = sv
    return (Y, U, V)


# ---------------------------------------------------------------- channels

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
        self.fallback = self._make_fallback(spec.get("logo"))
        self.latest = self.fallback
        self.fresh_until = 0.0
        self.running = True
        self.vcount = 0          # decoded video frames (for rate diagnostics)
        # audio buffer (only used when provides_audio)
        self.alock = threading.Lock()
        self.aframes = []        # list of (pts_s: float|None, ndarray(n,2) int16)
        self.abuffered = 0
        # video PTS clock anchor — updated by run(), read by audio_pts_now()
        self.clk_pts: "float | None" = None
        self.clk_wall: "float | None" = None

    def _make_fallback(self, logo):
        Y, U, V = black_planes(self.w, self.h)
        if logo:
            try:
                with av.open(logo) as c:
                    for frame in c.decode(video=0):
                        side = (min(self.w, self.h) // 3) & ~1
                        lf = frame.reformat(width=side, height=side, format="yuv420p")
                        ly, lu, lv = yuv_planes_from_frame(lf, side, side)
                        oy = ((self.h - side) // 2) & ~1
                        ox = ((self.w - side) // 2) & ~1
                        Y[oy:oy + side, ox:ox + side] = ly
                        U[oy // 2:(oy + side) // 2, ox // 2:(ox + side) // 2] = lu
                        V[oy // 2:(oy + side) // 2, ox // 2:(ox + side) // 2] = lv
                        break
            except Exception as e:  # noqa: BLE001
                log(f"logo decode failed for {self.name}: {e}")
        return (Y, U, V)

    def run(self):
        while self.running:
            cont = None
            # Flush stale audio and reset the PTS clock before each new
            # connection so old samples never bleed into the new stream.
            with self.alock:
                self.aframes.clear()
                self.abuffered = 0
            self.clk_pts = None
            self.clk_wall = None
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
                for packet in cont.demux(*streams):
                    if not self.running:
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
                            self.latest = fit_into_tile(frame, self.w, self.h)
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
            except Exception as e:  # noqa: BLE001
                log(f"channel {self.name} ended: {e}")
            finally:
                if cont is not None:
                    try:
                        cont.close()
                    except Exception:
                        pass
            if self.running:
                time.sleep(RECONNECT_BACKOFF)

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
                else:
                    out[filled:] = chunk[:need]
                    self.aframes[0] = (pts_s, chunk[need:])
                    self.abuffered -= need
                    filled = nsamples
        return out


# ---------------------------------------------------------------- encoder

def _write_all(fd, data):
    mv = memoryview(data)
    while mv:
        try:
            k = os.write(fd, mv)
        except OSError:
            return False
        mv = mv[k:]
    return True


def build_encoder_cmd(cfg, out_w, out_h, audio_read):
    bitrate = int(cfg.get("bitrate", 8000))
    gop = max(2, round(float(fps_fraction(cfg["fps"])) * 2))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
           # Cap encode threads so it doesn't grab every core and starve the
           # PyAV decoders (3x 1080p60 decode already loads the box).
           "-threads", str(cfg.get("enc_threads", 4)),
           "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{out_w}x{out_h}",
           "-r", cfg["fps"], "-thread_queue_size", "512", "-i", "pipe:0"]
    for r in audio_read:
        cmd += ["-f", "s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
                "-thread_queue_size", "512", "-i", f"pipe:{r}"]
    cmd += ["-map", "0:v:0"]
    for i in range(len(audio_read)):
        cmd += ["-map", f"{i + 1}:a:0"]
    # VBV CBR: -b:v == -minrate == -maxrate forces constant bitrate regardless of
    # content complexity. CRF (VBR) produces near-zero bitrate for static/logo
    # content; IPTV players drain their receive buffer faster than realtime when
    # data rate is very low, causing fast-forward on faster hardware. CBR pads
    # with H.264 filler NAL units to maintain constant rate.
    # bufsize = 0.5x target keeps encode latency low.
    # -muxrate is NOT used: with CBR the encoder already guarantees constant
    # output rate; adding -muxrate on top creates MPEG-TS null packets that
    # shift the PCR clock away from the video PTS, causing player sync issues.
    cmd += ["-c:v", "libx264", "-preset", cfg.get("preset") or "ultrafast",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{bitrate}k",
            "-minrate", f"{bitrate}k",
            "-maxrate", f"{bitrate}k",
            "-bufsize", f"{bitrate // 2}k",
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]
    if audio_read:
        cmd += ["-c:a", "ac3", "-b:a", "192k"]
    cmd += ["-max_muxing_queue_size", "1024",
            "-mpegts_flags", "+pat_pmt_at_frames+resend_headers+initial_discontinuity",
            "-flush_packets", "1", "-f", "mpegts", "pipe:1"]
    return cmd


def audio_feeder(track, fd, stop):
    CHUNK = int(AUDIO_RATE * 0.02)  # 960 samples = 20ms per tick
    SILENCE = np.zeros((CHUNK, 2), dtype=np.int16)

    # Phase 1: wait for the video PTS clock to establish, then snap the audio
    # buffer to that position. This discards any audio Dispatcharr pre-buffered
    # ahead of realtime before we start constant-rate output.
    while not stop.is_set():
        pts_now = track.audio_pts_now()
        if pts_now is not None:
            track._align_to_pts(pts_now - 0.10)
            break
        _write_all(fd, SILENCE.tobytes())
        time.sleep(0.02)

    # Phase 2: constant wall-clock rate. Smooth output is more important than
    # perfect PTS tracking; the reconnect flush in Channel.run() handles the
    # stale-audio problem, so wall-clock pacing is safe here.
    start = time.monotonic()
    written = 0
    while not stop.is_set():
        target = int((time.monotonic() - start) * AUDIO_RATE)
        need = target - written
        if need > 0:
            pcm = track.take(need)
            if not _write_all(fd, pcm.tobytes()):
                break
            written += need
        time.sleep(0.02)


# ---------------------------------------------------------------- main

def main():
    cfg = json.loads(sys.argv[1])
    out_w, out_h = cfg["out_w"], cfg["out_h"]
    fps_f = float(fps_fraction(cfg["fps"]))
    channels = [Channel(t) for t in cfg["tiles"]]
    audio_chs = [c for c in channels if c.provides_audio]
    stop = threading.Event()

    for c in channels:
        threading.Thread(target=c.run, name=f"chan-{c.name}", daemon=True).start()

    # ffmpeg encodes (libx264, multi-core C) + muxes; we feed it the composited
    # yuv420p canvas on stdin and one PCM track per audio channel on inherited fds.
    video_r, video_w = os.pipe()
    audio_pipes = [os.pipe() for _ in audio_chs]
    audio_read = [r for (r, _w) in audio_pipes]
    enc_out_r, enc_out_w = os.pipe()
    cmd = build_encoder_cmd(cfg, out_w, out_h, audio_read)
    for i, a in enumerate(audio_chs):
        cmd[-1:-1] = [f"-metadata:s:a:{i}", f"title={a.name}",
                      f"-metadata:s:a:{i}", f"language={a.lang}"]
    enc = subprocess.Popen(cmd, stdin=video_r, stdout=enc_out_w,
                           stderr=sys.stderr, pass_fds=audio_read)
    os.close(video_r)
    os.close(enc_out_w)
    for r in audio_read:
        os.close(r)
    audio_w = [w for (_r, w) in audio_pipes]

    # Forward the encoder's mpegts to our stdout (read by the plugin's server).
    def pump_out():
        wout = sys.stdout.buffer
        while True:
            b = os.read(enc_out_r, 65536)
            if not b:
                break
            try:
                wout.write(b)
                wout.flush()
            except (BrokenPipeError, ValueError):
                break
        stop.set()
    threading.Thread(target=pump_out, name="pump-out", daemon=True).start()

    for a, fd in zip(audio_chs, audio_w):
        threading.Thread(target=audio_feeder, args=(a, fd, stop), daemon=True).start()

    # yuv420p canvas as one flat buffer (Y|U|V) with plane views; writing the
    # whole buffer is exactly the planar byte order ffmpeg's rawvideo wants.
    ysize = out_w * out_h
    csize = (out_w // 2) * (out_h // 2)
    cbuf = np.zeros(ysize + 2 * csize, np.uint8)
    Yc, Uc, Vc = _yuv_planes(cbuf, out_w, out_h)
    Uc[:] = 128
    Vc[:] = 128

    start = time.monotonic()
    n = 0
    log_at = start + 30.0
    prev_t = start
    prev_counts = [0] * len(channels)
    log(f"started: {len(channels)} tiles, {len(audio_chs)} audio, {out_w}x{out_h}@{cfg['fps']}")
    try:
        while not stop.is_set():
            for t in channels:
                Yt, Ut, Vt = t.current()
                x, y, w, h = t.x, t.y, t.w, t.h
                Yc[y:y + h, x:x + w] = Yt
                Uc[y // 2:(y + h) // 2, x // 2:(x + w) // 2] = Ut
                Vc[y // 2:(y + h) // 2, x // 2:(x + w) // 2] = Vt
            if not _write_all(video_w, memoryview(cbuf)):
                break
            n += 1
            now = time.monotonic()
            if now >= log_at:   # heartbeat: per-channel decode fps (CPU health)
                dt = now - prev_t
                rates = " ".join(f"{c.name[:7]}={(c.vcount - prev_counts[i]) / dt:.0f}fps"
                                 for i, c in enumerate(channels))
                log(f"out {n / (now - start):.1f}fps; decode {rates}")
                prev_counts = [c.vcount for c in channels]
                prev_t = now
                log_at = now + 30.0
            delay = (start + n / fps_f) - now
            if delay > 0:
                time.sleep(delay)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        for c in channels:
            c.running = False
        try:
            os.close(video_w)
        except OSError:
            pass
        try:
            enc.wait(timeout=3)
        except Exception:
            enc.kill()


if __name__ == "__main__":
    main()
