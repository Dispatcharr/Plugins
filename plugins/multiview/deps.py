"""On-demand install of the vendored PyAV dependency.

Dispatcharr caps plugin import size (DISPATCHARR_PLUGIN_IMPORT_MAX_BYTES, default
200MB) and one PyAV wheel per arch is ~114MB, so we do NOT ship PyAV in the plugin
zip. Instead the plugin exposes "Install PyAV" actions that fetch the matching
wheel from PyPI at runtime and unpack it under vendor/<arch>/, where
compositor_worker.py loads it.

No pip is required (the container has none): we use the PyPI JSON API + urllib.
"""

import json
import logging
import os
import platform
import shutil
import tempfile
import urllib.request
import zipfile

logger = logging.getLogger(__name__)

PYAV_VERSION = "14.2.0"
PY_TAG = "cp313"

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(_PLUGIN_DIR, "vendor")

# vendor subdir -> machine aliases + the manylinux wheel arch token
ARCHES = {
    "linux-x86_64": {"machines": ("x86_64", "amd64"), "token": "x86_64"},
    "linux-aarch64": {"machines": ("aarch64", "arm64"), "token": "aarch64"},
}


def detect_arch() -> "str | None":
    """vendor subdir for this host, or None if unsupported."""
    m = platform.machine().lower()
    for arch, info in ARCHES.items():
        if m in info["machines"]:
            return arch
    return None


def arch_dir(arch: str) -> str:
    return os.path.join(VENDOR_DIR, arch)


def pyav_status(arch: str) -> "str | None":
    """Installed PyAV version string under vendor/<arch>, or None if absent."""
    d = arch_dir(arch)
    if not os.path.isdir(d):
        return None
    for name in os.listdir(d):
        if name.startswith("av-") and name.endswith(".dist-info"):
            return name[len("av-"):-len(".dist-info")]
    return "installed" if os.path.isdir(os.path.join(d, "av")) else None


def _find_wheel(arch: str):
    """Return (url, filename) of the cp313 manylinux wheel for this arch."""
    info = ARCHES[arch]
    api = f"https://pypi.org/pypi/av/{PYAV_VERSION}/json"
    with urllib.request.urlopen(api, timeout=30) as r:
        data = json.load(r)
    for f in data.get("urls", []):
        fn = f.get("filename", "")
        if (fn.endswith(".whl") and f"-{PY_TAG}-" in fn
                and "manylinux" in fn and info["token"] in fn):
            return f["url"], fn
    raise RuntimeError(
        f"no {PY_TAG} manylinux {info['token']} wheel in av {PYAV_VERSION} on PyPI")


def install_pyav(arch: str) -> dict:
    """Download + unpack the PyAV wheel for `arch` into vendor/<arch>/."""
    if arch not in ARCHES:
        return {"status": "error", "message": f"Unsupported arch: {arch!r}"}
    try:
        url, fn = _find_wheel(arch)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"multiview: PyAV wheel lookup failed: {e}")
        return {"status": "error", "message": f"Could not find PyAV wheel: {e}"}

    tmp = tempfile.mkdtemp(prefix="mv-pyav-")
    try:
        whl = os.path.join(tmp, fn)
        logger.info(f"multiview: downloading {fn} for {arch}...")
        urllib.request.urlretrieve(url, whl)
        dest = arch_dir(arch)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(whl) as z:
            z.extractall(dest)
    except PermissionError as e:
        logger.error(f"multiview: PyAV install permission error: {e}")
        return {"status": "error", "message": (
            f"Install failed (permission denied writing {VENDOR_DIR}). The plugin "
            f"directory must be writable by the Dispatcharr user. Details: {e}")}
    except Exception as e:  # noqa: BLE001
        logger.error(f"multiview: PyAV install failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Install failed: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ver = pyav_status(arch) or PYAV_VERSION
    msg = f"PyAV {ver} installed for {arch}."
    logger.info(f"multiview: {msg}")
    return {"status": "success", "message": msg}
