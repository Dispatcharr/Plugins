"""Inspect external releases using the same directory choice as Dispatcharr."""

import argparse
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def inspect_archive(archive):
    """Return the manifest entry, parsed manifest and selected directory prefix."""
    files = {}
    manifests = []
    for entry in archive.infolist():
        name = entry.filename
        parts = name.rstrip("/").split("/")
        mode = entry.external_attr >> 16
        if (not name or "\\" in name or any(p in ("", ".", "..") for p in parts)
                or stat.S_ISLNK(mode)):
            raise ValueError("Release ZIP contains an unsafe path")
        if entry.is_dir():
            continue
        if name in files:
            raise ValueError("Release ZIP contains duplicate paths or manifests")
        files[name] = entry
        if parts[-1] == "plugin.json" and len(parts) <= 2:
            manifests.append(entry)
    if len(manifests) != 1:
        raise ValueError("Release ZIP must contain exactly one candidate `plugin.json` at the root or one directory below it")
    # Files cannot also be parent directories after extraction.
    for name in files:
        if any(str(parent) in files for parent in PurePosixPath(name).parents if str(parent) != "."):
            raise ValueError("Release ZIP contains conflicting paths")
    manifest_entry = manifests[0]
    prefix = manifest_entry.filename[:-len("plugin.json")]
    candidates = []
    for name in files:
        path = PurePosixPath(name)
        if path.name in ("plugin.py", "__init__.py"):
            directory = str(path.parent)
            directory = "" if directory == "." else directory + "/"
            depth = 1 if not directory else len(path.parts) - 1
            candidates.append((0 if path.name == "plugin.py" else 1, depth, directory))
    if not candidates or min(candidates)[2] != prefix:
        raise ValueError("Release manifest must be in the plugin directory selected by Dispatcharr (plugin.py or __init__.py)")
    with archive.open(manifest_entry) as source:
        manifest = json.load(source)
    if not isinstance(manifest, dict):
        raise ValueError("Release `plugin.json` must be a JSON object")
    return manifest_entry, manifest, prefix


def stage_release(artifact, plugin_dir):
    """Replace catalog source with the selected release source for CodeQL."""
    plugin_dir = Path(plugin_dir)
    if plugin_dir.is_symlink() or (plugin_dir / "plugin.json").is_symlink():
        raise ValueError("Catalog plugin directory and manifest must not be symlinks")
    catalog = (plugin_dir / "plugin.json").read_bytes()
    with zipfile.ZipFile(artifact) as archive, tempfile.TemporaryDirectory() as tmp:
        manifest_entry, _, prefix = inspect_archive(archive)
        staged = Path(tmp) / "plugin"
        staged.mkdir()
        (staged / "plugin.json").write_bytes(catalog)
        (staged / ".dispatcharr-runtime-manifest.json").write_bytes(archive.read(manifest_entry))
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.startswith(prefix):
                continue
            relative = entry.filename[len(prefix):]
            if relative == "plugin.json":
                continue
            if relative == ".dispatcharr-runtime-manifest.json" or relative.startswith(("plugin.json/", ".dispatcharr-runtime-manifest.json/")):
                raise ValueError("Release ZIP conflicts with reserved manifest paths")
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)
        shutil.rmtree(plugin_dir)
        shutil.copytree(staged, plugin_dir)


def main():
    parser = argparse.ArgumentParser(description="Stage an external release for CodeQL")
    parser.add_argument("artifact")
    parser.add_argument("plugin_dir")
    args = parser.parse_args()
    stage_release(args.artifact, args.plugin_dir)


if __name__ == "__main__":
    main()
