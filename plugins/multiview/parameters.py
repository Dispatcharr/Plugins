"""FFmpeg encoder parameter construction and validation for the compositor worker."""

import glob
import subprocess
import sys
from fractions import Fraction

try:
    from .config import ENCODER_PRESETS
except ImportError:
    from config import ENCODER_PRESETS  # script context (compositor_worker.py)

# Must match channel.py AUDIO_RATE.
AUDIO_RATE = 48000

_COMPOSITOR_PROBES = {}
_COMPOSITOR_FAILURES = {}


def fps_fraction(fps: str) -> Fraction:
    if "/" in fps:
        a, b = fps.split("/")
        return Fraction(int(a), int(b))
    return Fraction(int(fps), 1)


def _find_dri_device(override: str = "") -> str:
    if override and override != "auto":
        return override
    devices = sorted(glob.glob("/dev/dri/render*"))
    return devices[0] if devices else "/dev/dri/renderD128"


def _encoder_available(name: str) -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
        )
        return name in r.stdout
    except Exception:
        return False


def resolve_preset(encoder: str, saved) -> str:
    """Return a validated preset string for the given encoder."""
    valid, default = ENCODER_PRESETS.get(encoder, (frozenset(), "ultrafast"))
    return saved if (valid and saved in valid) else default


def validate_encoder(encoder: str) -> None:
    """sys.exit if the selected hardware encoder is unavailable."""
    _checks = {
        "h264_nvenc": ("NVENC", "check NVIDIA driver and ffmpeg build"),
        "h264_qsv":   ("QSV",   "check Intel driver and ffmpeg build"),
        "h264_vaapi": ("VAAPI", "check GPU driver and ffmpeg build"),
    }
    if encoder in _checks and not _encoder_available(encoder):
        name, hint = _checks[encoder]
        sys.exit(f"{encoder} selected but ffmpeg reports no {name} encoder -- {hint}")


def gpu_compositor(cfg: dict) -> "dict | None":
    """Return the supported hardware compositor for *cfg*, else None.

    The PyAV workers still own source decode and PTS selection. This path moves
    the final tile placement into ffmpeg's vendor hardware filters. A missing
    filter or inaccessible device must not turn a usable hardware encoder into
    an unavailable stream, so callers fall back to the CPU compositor.
    """
    encoder = cfg.get("video_encoder", "libx264")
    specs = {
        "h264_nvenc": {
            "name": "cuda", "filters": ("hwupload_cuda", "overlay_cuda"),
            "init": ["-init_hw_device", "cuda=mv", "-filter_hw_device", "mv"],
            "probe_graph": "[0:v]hwupload_cuda[a];[1:v]hwupload_cuda[b];[a][b]overlay_cuda[mvout]",
        },
        "h264_vaapi": {
            "name": "vaapi", "filters": ("hwupload", "xstack_vaapi"),
            "init": ["-vaapi_device", _find_dri_device(cfg.get("render_device", ""))],
            "probe_graph": "[0:v]format=nv12,hwupload[a];[1:v]format=nv12,hwupload[b];[a][b]xstack_vaapi=inputs=2:layout=0_0|16_0[mvout]",
        },
        "h264_qsv": {
            "name": "qsv", "filters": ("hwupload", "xstack_qsv"),
            "init": ["-init_hw_device", f"qsv=mv:{_find_dri_device(cfg.get('render_device', ''))}",
                     "-filter_hw_device", "mv"],
            "probe_graph": "[0:v]format=nv12,hwupload=extra_hw_frames=2[a];[1:v]format=nv12,hwupload=extra_hw_frames=2[b];[a][b]xstack_qsv=inputs=2:layout=0_0|16_0[mvout]",
        },
    }
    spec = specs.get(encoder)
    if spec is None:
        return None
    if cfg.get("background"):
        return None

    key = (encoder, cfg.get("render_device", ""))
    if key in _COMPOSITOR_PROBES:
        return _COMPOSITOR_PROBES[key]
    try:
        filters = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True,
            text=True, timeout=5,
        ).stdout
        missing = [name for name in spec["filters"] if name not in filters]
        if missing:
            result = None
            reason = f"missing FFmpeg filter(s): {', '.join(missing)}"
        else:
            # Filter listing only says the binary was compiled with support.
            # Exercise the exact upload and composition primitives before
            # selecting this path, so a broken FFmpeg build falls back safely.
            probe = ["ffmpeg", "-hide_banner", "-loglevel", "error", *spec["init"],
                     "-f", "lavfi", "-i", "color=black:s=16x16:r=1",
                     "-f", "lavfi", "-i", "color=black:s=16x16:r=1",
                     "-filter_complex", spec["probe_graph"], "-map", "[mvout]",
                     "-frames:v", "1", "-f", "null", "-"]
            check = subprocess.run(probe, capture_output=True, text=True, timeout=10)
            result = spec if check.returncode == 0 else None
            reason = "GPU device/filter graph probe failed" if result is None else None
    except Exception as e:
        result = None
        reason = f"GPU compositor probe failed: {e}"
    _COMPOSITOR_PROBES[key] = result
    if result is None:
        _COMPOSITOR_FAILURES[key] = reason
    return result


def gpu_compositor_failure(cfg: dict) -> str:
    """Return the last automatic-fallback reason for a hardware profile."""
    if cfg.get("video_encoder", "libx264") == "libx264":
        return "software encoder selected"
    if cfg.get("background"):
        return "background image requires CPU composition"
    return _COMPOSITOR_FAILURES.get(
        (cfg.get("video_encoder", "libx264"), cfg.get("render_device", "")),
        "GPU filters/device unavailable",
    )


def build_encoder_cmd(cfg, out_w, out_h, audio_read, video_inputs=None, compositor=None) -> list:
    bitrate = int(cfg.get("bitrate", 8000))
    gop = max(2, round(float(fps_fraction(cfg["fps"])) * 2))
    encoder = cfg.get("video_encoder", "libx264")
    preset = resolve_preset(encoder, cfg.get("preset"))
    render_device = cfg.get("render_device", "")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]

    # Hardware device init must precede inputs. GPU composition may need a
    # named device as well as the encoder itself.
    if compositor:
        cmd += compositor["init"]
    elif encoder == "h264_vaapi":
        cmd += ["-vaapi_device", _find_dri_device(render_device)]
    elif encoder == "h264_qsv":
        cmd += ["-init_hw_device", f"qsv=hw:{_find_dri_device(render_device)}", "-filter_hw_device", "hw"]

    # Cap muxer/filter threads so it doesn't grab every core and starve
    # the PyAV decoders (3x 1080p60 decode already loads the box).
    cmd += ["-threads", str(cfg.get("enc_threads", 4))]
    if video_inputs:
        for fd, w, h in video_inputs:
            cmd += ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{w}x{h}",
                    "-r", cfg["fps"], "-thread_queue_size", "8", "-i", f"pipe:{fd}"]
        if compositor["name"] == "cuda":
            # CUDA has overlay but no xstack equivalent. A generated black
            # canvas is the base for ordered tile overlays.
            cmd += ["-f", "lavfi", "-i", f"color=black:s={out_w}x{out_h}:r={cfg['fps']}"]
    else:
        cmd += ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{out_w}x{out_h}",
                "-r", cfg["fps"], "-thread_queue_size", "512", "-i", "pipe:0"]
    for r in audio_read:
        cmd += ["-f", "s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
                "-thread_queue_size", "512", "-i", f"pipe:{r}"]
    if video_inputs:
        graph = _gpu_filtergraph(video_inputs, cfg["tiles"], out_w, out_h, compositor)
        cmd += ["-filter_complex", graph, "-map", "[mvout]"]
        audio_offset = len(video_inputs) + (1 if compositor["name"] == "cuda" else 0)
    else:
        cmd += ["-map", "0:v:0"]
        audio_offset = 1
    for i in range(len(audio_read)):
        cmd += ["-map", f"{audio_offset + i}:a:0"]

    # VBV CBR: constant bitrate regardless of content complexity. CRF (VBR)
    # produces near-zero bitrate for static/logo content; IPTV players drain
    # their receive buffer faster than realtime when the rate is very low,
    # causing fast-forward. CBR pads with filler NAL units to hold constant
    # rate. bufsize = 0.5x target keeps encode latency low.
    # -muxrate is NOT used: CBR already guarantees constant output rate;
    # -muxrate adds MPEG-TS null packets that shift the PCR clock away from
    # video PTS, causing player sync issues.
    if encoder == "h264_nvenc":
        # NVENC CBR via -rc cbr (pads with filler NAL units, same guarantee as
        # x264 CBR). -minrate, -keyint_min, -sc_threshold are x264-only.
        video_args = ["-c:v", "h264_nvenc", "-preset", preset,
                      "-rc", "cbr"]
        # A CUDA filtergraph already produces CUDA frames. Forcing yuv420p
        # here makes ffmpeg insert a software download between overlay_cuda
        # and NVENC, which the graph cannot negotiate. CPU composition still
        # needs the encoder's software input format selected explicitly.
        if not compositor:
            video_args += ["-pix_fmt", "yuv420p"]
        cmd += video_args + ["-b:v", f"{bitrate}k",
                             "-maxrate", f"{bitrate}k",
                             "-bufsize", f"{bitrate // 2}k",
                             "-g", str(gop)]
    elif encoder == "h264_vaapi":
        # VAAPI CBR: yuv420p input must be converted to nv12 before hwupload.
        # -rc_mode CBR enforces constant rate; driver pads output to hold bitrate.
        if not compositor:
            cmd += ["-vf", "format=nv12,hwupload"]
        cmd += [
                "-c:v", "h264_vaapi",
                "-rc_mode", "CBR",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{bitrate}k",
                "-bufsize", f"{bitrate // 2}k",
                "-g", str(gop)]
    elif encoder == "h264_qsv":
        # QSV CBR: hwupload sends software frames to QSV device initialized above.
        if not compositor:
            cmd += ["-vf", "format=nv12,hwupload=extra_hw_frames=64"]
        cmd += [
                "-c:v", "h264_qsv",
                "-preset", preset,
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{bitrate}k",
                "-bufsize", f"{bitrate // 2}k",
                "-g", str(gop)]
    else:
        cmd += ["-c:v", "libx264", "-preset", preset,
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


def _gpu_filtergraph(video_inputs, tiles, out_w, out_h, compositor) -> str:
    """Build the vendor graph for fixed-size, already letterboxed tile frames."""
    name = compositor["name"]
    if name == "cuda":
        chains = [f"[{len(video_inputs)}:v]hwupload_cuda[base]"]
        previous = "base"
        for i, tile in enumerate(tiles):
            chains.append(f"[{i}:v]hwupload_cuda[t{i}]")
            out = "mvout" if i == len(tiles) - 1 else f"o{i}"
            chains.append(f"[{previous}][t{i}]overlay_cuda=x={tile['x']}:y={tile['y']}[{out}]")
            previous = out
        return ";".join(chains)

    uploaded = []
    for i in range(len(video_inputs)):
        label = f"t{i}"
        upload = "format=nv12,hwupload=extra_hw_frames=64" if name == "qsv" else "format=nv12,hwupload"
        chains = [f"[{i}:v]{upload}[{label}]"]
        uploaded.append(f"[{label}]")
        if i == 0:
            all_chains = chains
        else:
            all_chains.extend(chains)
    layout = "|".join(f"{tile['x']}_{tile['y']}" for tile in tiles)
    all_chains.append(f"{''.join(uploaded)}xstack_{name}=inputs={len(video_inputs)}:layout={layout}:fill=black[mvout]")
    return ";".join(all_chains)
