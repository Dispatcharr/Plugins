"""Multiview compositor worker (separate process, no gevent).

Spawned by server._serve_stream as `python compositor_worker.py <config-json>`. It
runs as a plain CPython process (so real threads parallelize across cores and
nothing fights Dispatcharr's gevent hub). Config schema (argv[1] JSON):

  {"out_w","out_h","fps","bitrate","crf","preset",
   "tiles":[{"url","x","y","w","h","logo","name"}...],
   "audio":[{"url","name","lang"}...]}

The Channel class (decode, YUV compositing, audio buffering) and its PyAV/numpy
dependencies live in channel.py. Encoder construction and hardware detection live
in parameters.py. This module handles the main compositing loop.
"""

import json
import os
import subprocess
import sys
import threading
import time

# channel.py sets up the vendored PyAV sys.path as a side effect of import;
# numpy must be imported after so it finds the vendored build.
from channel import Channel, AUDIO_RATE, AUDIO_LAYOUT, log, _yuv_planes, yuv_planes_from_frame, _even  # noqa: E402

import av  # noqa: E402  (vendored, already on sys.path via the channel import above)
import numpy as np  # noqa: E402

from parameters import fps_fraction, build_encoder_cmd, validate_encoder  # noqa: E402

DRIFT_THRESHOLD = 0.25  # seconds of audio-behind-video before we skip the
                         # FIFO forward to re-sync (see audio_feeder())


# ---------------------------------------------------------------- compositing helpers

def _write_all(fd, data):
    mv = memoryview(data)
    while mv:
        try:
            k = os.write(fd, mv)
        except OSError:
            return False
        mv = mv[k:]
    return True


def stdin_listener(channels, stop):
    """Read JSON control commands from stdin (sent by the plugin server)."""
    for line in sys.stdin:
        if stop.is_set():
            break
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except Exception:
            continue
        if cmd.get("cmd") == "reconnect_channel":
            idx = cmd.get("idx")
            if idx is not None and 0 <= idx < len(channels):
                log(f"reconnect requested: channel {idx} ({channels[idx].name})")
                channels[idx].reconnect()
        elif cmd.get("cmd") == "reconnect_all":
            log("reconnect all channels requested")
            for c in channels:
                c.reconnect()


def audio_feeder(track, fd, stop):
    CHUNK = int(AUDIO_RATE * 0.02)  # 960 samples = 20ms per tick
    SILENCE = np.zeros((CHUNK, 2), dtype=np.int16)

    start = None
    written = 0
    snapped = False
    was_valid = False

    while not stop.is_set():
        pts_now = track.audio_pts_now()

        if pts_now is None:
            if was_valid:
                # Clock just went None -- reconnect in progress; reset snap state
                # so we re-anchor when the new stream establishes its first frame.
                snapped = False
                start = None
                written = 0
            was_valid = False
            _write_all(fd, SILENCE.tobytes())
            time.sleep(0.02)
            continue

        if not snapped:
            # New clock available (startup or post-reconnect): snap audio buffer
            # to current video PTS and reset wall-clock counters.
            track._align_to_pts(pts_now - 0.10)
            start = time.monotonic()
            written = 0
            snapped = True

        was_valid = True

        # Only correct audio-behind-video (silent underruns falling further
        # back over time); a transient audio-ahead-of-video reading is
        # self-limiting (FIFO capped by _trim(), audio never paced faster
        # than real time) and left uncorrected, matching the pre-existing
        # one-shot snap behavior which is also catch-up-only.
        last_pts = track.last_taken_pts
        if last_pts is not None and (pts_now - last_pts) > DRIFT_THRESHOLD:
            track._align_to_pts(pts_now - 0.10)

        target = int((time.monotonic() - start) * AUDIO_RATE)
        need = target - written
        if need > 0:
            pcm = track.take(need)
            if not _write_all(fd, pcm.tobytes()):
                break
            written += need
        time.sleep(0.02)


# ---------------------------------------------------------------- background image

def _load_background(path, out_w, out_h):
    """Decode a still image and scale+center-crop it to exactly out_w x out_h
    (aspect-preserving cover, like CSS background-size: cover), returning
    (Y, U, V) planes ready to seed the canvas once at startup. Same PyAV
    decode-to-YUV technique as channel.py's _make_fallback (logo image),
    just cover-fit instead of contain-fit since this fills the whole frame
    rather than a small padded tile.
    """
    with av.open(path) as c:
        for frame in c.decode(video=0):
            scale = max(out_w / frame.width, out_h / frame.height)
            sw, sh = _even(round(frame.width * scale)), _even(round(frame.height * scale))
            rf = frame.reformat(width=sw, height=sh, format="yuv420p")
            y, u, v = yuv_planes_from_frame(rf, sw, sh)
            ox = ((sw - out_w) // 2) & ~1
            oy = ((sh - out_h) // 2) & ~1
            Y = np.ascontiguousarray(y[oy:oy + out_h, ox:ox + out_w])
            U = np.ascontiguousarray(u[oy // 2:(oy + out_h) // 2, ox // 2:(ox + out_w) // 2])
            V = np.ascontiguousarray(v[oy // 2:(oy + out_h) // 2, ox // 2:(ox + out_w) // 2])
            return (Y, U, V)
    return None


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
    threading.Thread(target=stdin_listener, args=(channels, stop), name="stdin-ctrl", daemon=True).start()

    # ffmpeg encodes (libx264, multi-core C) + muxes; we feed it the composited
    # yuv420p canvas on stdin and one PCM track per audio channel on inherited fds.
    video_r, video_w = os.pipe()
    audio_pipes = [os.pipe() for _ in audio_chs]
    audio_read = [r for (r, _w) in audio_pipes]
    enc_out_r, enc_out_w = os.pipe()
    validate_encoder(cfg.get("video_encoder", "libx264"))
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

    # Seed the canvas with a background image once, if configured. Kept as
    # an immutable reference copy (bg_buf) alongside the live canvas: each
    # frame, every tile's rect is restored from this copy before its actual
    # content is blitted on top, so letterbox/pillarbox padding (and any
    # gap a layout leaves uncovered) shows the background instead of a
    # stale opaque-black bar painted over it by a previous frame.
    bg_path = cfg.get("background")
    if bg_path:
        try:
            bg = _load_background(bg_path, out_w, out_h)
            if bg:
                Yc[:], Uc[:], Vc[:] = bg
        except Exception as e:  # noqa: BLE001
            log(f"background image load failed ({bg_path}): {e}")

    bg_buf = cbuf.copy()
    bg_Y, bg_U, bg_V = _yuv_planes(bg_buf, out_w, out_h)

    start = time.monotonic()
    n = 0
    log_at = start + 30.0
    prev_t = start
    prev_counts = [0] * len(channels)
    log(f"started: {len(channels)} tiles, {len(audio_chs)} audio, {out_w}x{out_h}@{cfg['fps']}")
    try:
        while not stop.is_set():
            for t in channels:
                Yt, Ut, Vt, ox, oy, tw, th = t.current()
                x, y, w, h = t.x, t.y, t.w, t.h
                Yc[y:y + h, x:x + w] = bg_Y[y:y + h, x:x + w]
                Uc[y // 2:(y + h) // 2, x // 2:(x + w) // 2] = bg_U[y // 2:(y + h) // 2, x // 2:(x + w) // 2]
                Vc[y // 2:(y + h) // 2, x // 2:(x + w) // 2] = bg_V[y // 2:(y + h) // 2, x // 2:(x + w) // 2]
                px, py = x + ox, y + oy
                Yc[py:py + th, px:px + tw] = Yt
                Uc[py // 2:(py + th) // 2, px // 2:(px + tw) // 2] = Ut
                Vc[py // 2:(py + th) // 2, px // 2:(px + tw) // 2] = Vt
            if not _write_all(video_w, memoryview(cbuf)):
                break
            n += 1
            now = time.monotonic()
            if now >= log_at:   # heartbeat: per-channel decode fps (CPU health)
                dt = now - prev_t
                rates = " ".join(f"{c.name[:7]}={(c.vcount - prev_counts[i]) / dt:.0f}fps"
                                 for i, c in enumerate(channels))
                import resource as _res
                rss_mb = _res.getrusage(_res.RUSAGE_SELF).ru_maxrss // 1024
                log(f"out {n / (now - start):.1f}fps; decode {rates}; rss={rss_mb}MB")
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
        for fd in audio_w:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.close(video_w)
        except OSError:
            pass
        try:
            enc.wait(timeout=3)
        except Exception:
            enc.kill()
        try:
            os.close(enc_out_r)
        except OSError:
            pass


if __name__ == "__main__":
    main()
