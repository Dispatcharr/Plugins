"""Output media-settings helpers (resolution / frame rate).

The actual decode/compose/encode pipeline lives in compositor_worker.py (PyAV +
a libx264 ffmpeg subprocess). This module just parses the user's output settings
for server._worker_config.
"""

_FPS_CHOICES = {"24", "25", "30", "50", "60", "30000/1001", "60000/1001"}


def fps_string(settings: dict) -> str:
    """Output/sampling frame rate as a string (validated against the choices)."""
    v = str(settings.get("output_fps") or "30")
    return v if v in _FPS_CHOICES else "30"


def fps_value(fps: str) -> float:
    if "/" in fps:
        a, b = fps.split("/")
        return float(a) / float(b)
    return float(fps)


def _parse_resolution(settings: dict) -> tuple:
    try:
        w, h = (int(x) for x in (settings.get("output_resolution") or "1920x1080").split("x"))
        return w, h
    except Exception:
        return 1920, 1080
