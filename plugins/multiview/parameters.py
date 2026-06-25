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


def fps_fraction(fps: str) -> Fraction:
    if "/" in fps:
        a, b = fps.split("/")
        return Fraction(int(a), int(b))
    return Fraction(int(fps), 1)


def _find_dri_device() -> str:
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


def build_encoder_cmd(cfg, out_w, out_h, audio_read) -> list:
    bitrate = int(cfg.get("bitrate", 8000))
    gop = max(2, round(float(fps_fraction(cfg["fps"])) * 2))
    encoder = cfg.get("video_encoder", "libx264")
    preset = resolve_preset(encoder, cfg.get("preset"))

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]

    # Hardware device init must precede inputs.
    if encoder == "h264_vaapi":
        cmd += ["-vaapi_device", _find_dri_device()]
    elif encoder == "h264_qsv":
        cmd += ["-init_hw_device", f"qsv=hw:{_find_dri_device()}", "-filter_hw_device", "hw"]

    # Cap muxer/filter threads so it doesn't grab every core and starve
    # the PyAV decoders (3x 1080p60 decode already loads the box).
    cmd += ["-threads", str(cfg.get("enc_threads", 4)),
            "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{out_w}x{out_h}",
            "-r", cfg["fps"], "-thread_queue_size", "512", "-i", "pipe:0"]
    for r in audio_read:
        cmd += ["-f", "s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
                "-thread_queue_size", "512", "-i", f"pipe:{r}"]
    cmd += ["-map", "0:v:0"]
    for i in range(len(audio_read)):
        cmd += ["-map", f"{i + 1}:a:0"]

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
        cmd += ["-c:v", "h264_nvenc", "-preset", preset,
                "-rc", "cbr",
                "-pix_fmt", "yuv420p",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{bitrate}k",
                "-bufsize", f"{bitrate // 2}k",
                "-g", str(gop)]
    elif encoder == "h264_vaapi":
        # VAAPI CBR: yuv420p input must be converted to nv12 before hwupload.
        # -rc_mode CBR enforces constant rate; driver pads output to hold bitrate.
        cmd += ["-vf", "format=nv12,hwupload",
                "-c:v", "h264_vaapi",
                "-rc_mode", "CBR",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{bitrate}k",
                "-bufsize", f"{bitrate // 2}k",
                "-g", str(gop)]
    elif encoder == "h264_qsv":
        # QSV CBR: hwupload sends software frames to QSV device initialized above.
        cmd += ["-vf", "format=nv12,hwupload=extra_hw_frames=64",
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
