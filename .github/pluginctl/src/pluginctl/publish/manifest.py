"""Manifest construction, byte-for-byte equivalent to generate-manifest.sh.

The pure builders here assemble ``dict`` objects in the *exact* key order of the
jq programs in the Bash script and drop ``None`` the way
``with_entries(select(.value != null))`` does, so ``jsonio.dumps`` reproduces the
compact ``jq -c`` output. GPG signing and the "only re-sign when the payload
changed" logic are preserved in :func:`write_manifest_if_changed` /
:func:`sign_manifest`.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import tempfile
from typing import Optional

from .. import capabilities, feature_flags, messages, runtime_manifest
from ..core import jsonio
from ..core.jsonio import drop_none
from ..core.timeutil import now_iso
from ..core.version import higher_dispatcharr_version, versioned_tags
from . import ai_assisted


def _metadata_fields(metadata: dict, min_da, max_da) -> dict:
    """The build-metadata fields shared by ``versions[]`` and ``latest`` entries.

    Key order matters: it is the jq emission order the Bash script produced.
    """
    return {
        "version": metadata.get("version"),
        "prerelease": True if metadata.get("prerelease") is True else None,
        "commit_sha": metadata.get("commit_sha"),
        "commit_sha_short": metadata.get("commit_sha_short"),
        "changelog": metadata.get("changelog"),
        "build_timestamp": metadata.get("build_timestamp"),
        "last_updated": metadata.get("last_updated"),
        "checksum_md5": metadata.get("checksum_md5"),
        "checksum_sha256": metadata.get("checksum_sha256"),
        "min_dispatcharr_version": min_da,
        "max_dispatcharr_version": max_da,
        "source_url": metadata.get("source_url"),
    }


def effective_min_dispatcharr_version(plugin_dir: str, plugin_raw: dict) -> str:
    """Return the higher catalog or versioned-runtime-manifest minimum."""
    declared_minimum = str(plugin_raw.get("min_dispatcharr_version") or "")
    manifest = runtime_manifest.load(plugin_dir, plugin_raw)
    if manifest is None or not capabilities.manifest_version_is_valid(manifest):
        return declared_minimum
    schema_minimum = capabilities.manifest_version_min_app_version(
        capabilities.parse_manifest_version(manifest)
    )
    return higher_dispatcharr_version(declared_minimum, schema_minimum) or ""


def build_version_entry(metadata: dict, url: str, size, canonical_version: str,
                        download_count: Optional[int] = None) -> dict:
    """A ``versions[]`` entry.

    With metadata present, all fields are populated (nulls dropped). With empty
    metadata the Bash else-branch emits only ``{version,url,size}`` using the
    tag-derived canonical version.
    """
    if metadata:
        return drop_none({
            **_metadata_fields(metadata,
                               metadata.get("min_dispatcharr_version"),
                               metadata.get("max_dispatcharr_version")),
            "url": url,
            "size": size,
            "download_count": download_count,
        })
    return drop_none({
        "version": canonical_version,
        "url": url,
        "size": size,
        "download_count": download_count,
    })


def override_current_min_max(versioned_zips: list[dict], current_version: str,
                             min_da: str, max_da: str) -> list[dict]:
    """Overlay plugin.json min/max onto the current version's entry (metadata-only updates)."""
    out = []
    for entry in versioned_zips:
        if entry.get("version") == current_version:
            merged = dict(entry)
            merged["min_dispatcharr_version"] = min_da if min_da != "" else None
            merged["max_dispatcharr_version"] = max_da if max_da != "" else None
            out.append(drop_none(merged))
        else:
            out.append(entry)
    return out


def build_plugin_entry(plugin_raw: dict, plugin_name: str, latest_url: str,
                        registry_url: str, registry_name: str,
                        versioned_zips: list[dict], latest_metadata: dict,
                        latest_size_kb, ai_assisted_disclosed: bool = False,
                        download_count: Optional[int] = None,
                        latest_download_count: Optional[int] = None,
                        min_da: Optional[str] = None,
                        max_da: Optional[str] = None) -> dict:
    """Per-plugin manifest ``.manifest`` payload (metadata/<slug>/manifest.json)."""
    def g(key):
        return plugin_raw.get(key)

    effective_min_da = g("min_dispatcharr_version") if min_da is None else min_da
    effective_max_da = g("max_dispatcharr_version") if max_da is None else max_da
    latest = None
    if latest_metadata:
        latest = drop_none({
            **_metadata_fields(latest_metadata,
                               effective_min_da,
                               effective_max_da),
            "latest_url": latest_url,
            "url": versioned_zips[0]["url"] if versioned_zips else None,
            "size": latest_size_kb,
            "download_count": latest_download_count,
        })

    return drop_none({
        "slug": plugin_name,
        "name": g("name"),
        "description": g("description"),
        "author": g("author"),
        "maintainers": g("maintainers"),
        "license": g("license"),
        "ai_assisted": True if ai_assisted_disclosed else None,
        "deprecated": True if g("deprecated") is True else None,
        "source_type": "external" if g("source_type") == "external" else None,
        "source_url": g("source_url"),
        "repo_url": g("repo_url"),
        "discord_thread": g("discord_thread"),
        "registry_url": registry_url,
        "registry_name": registry_name,
        "last_updated": latest_metadata.get("last_updated") if latest_metadata else None,
        "download_count": download_count,
        "latest": latest,
        "versions": versioned_zips,
    })


def trim_description(desc: str) -> str:
    """``desc[:197] + "..."`` when longer than 200 chars, else unchanged."""
    return (desc[:197] + "...") if len(desc) > 200 else desc


def build_root_entry(plugin_raw: dict, plugin_name: str, latest_metadata: dict,
                       latest_size_kb, min_da: str, max_da: str,
                       latest_url: str, manifest_url: str,
                       ai_assisted_disclosed: bool = False,
                       download_count: Optional[int] = None) -> dict:
    """Compact entry for the root manifest's ``plugins[]``."""
    license_id = plugin_raw.get("license") or ""
    return drop_none({
        "slug": plugin_name,
        "name": plugin_raw.get("name") or "",
        "description": trim_description(plugin_raw.get("description") or ""),
        "manifest_url": manifest_url,
        "author": plugin_raw.get("author") or "",
        "license": license_id if license_id != "" else None,
        "ai_assisted": True if ai_assisted_disclosed else None,
        "deprecated": True if plugin_raw.get("deprecated") is True else None,
        "last_updated": latest_metadata.get("last_updated") if latest_metadata else None,
        "download_count": download_count,
        "latest_version": latest_metadata.get("version") if latest_metadata else None,
        "latest_changelog": latest_metadata.get("changelog") if latest_metadata else None,
        "latest_md5": latest_metadata.get("checksum_md5") if latest_metadata else None,
        "latest_sha256": latest_metadata.get("checksum_sha256") if latest_metadata else None,
        "latest_url": latest_url,
        "latest_size": latest_size_kb if _num(latest_size_kb) > 0 else None,
        "min_dispatcharr_version": min_da if min_da != "" else None,
        "max_dispatcharr_version": max_da if max_da != "" else None,
    })


def build_root_manifest(registry_url: str, registry_name: str, download_base_url: str,
                         root_entries: list[dict], metadata_base_url: Optional[str] = None,
                         registry_messages: Optional[list[dict]] = None) -> dict:
    root = {
        "registry_url": registry_url,
        "registry_name": registry_name,
    }
    if metadata_base_url is None:
        root["root_url"] = download_base_url
    else:
        root["download_base_url"] = download_base_url
        root["metadata_base_url"] = metadata_base_url
    root["messages"] = registry_messages if registry_messages is not None else []
    root["plugins"] = root_entries
    return root


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ---- on-disk wrapper + GPG signing ------------------------------------------
def write_manifest_if_changed(dest: str, payload: dict, generated_at: str) -> bool:
    """Write ``{generated_at, manifest}`` only if the compact payload changed.

    Returns True if written, False if skipped (unchanged), mirroring the Bash
    return codes that gate re-signing.
    """
    new_compact = jsonio.dumps(payload)
    if os.path.isfile(dest):
        try:
            with open(dest, encoding="utf-8") as fh:
                existing = json.load(fh)
            if jsonio.dumps(existing.get("manifest")) == new_compact:
                return False
        except (OSError, ValueError):
            pass
    wrapper = {"generated_at": generated_at, "manifest": json.loads(new_compact)}
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(jsonio.dumps_formatted(wrapper))
    return True


def _signing_payload(manifest: dict) -> str:
    """Return the canonical bytes reconstructed by Dispatcharr for verification."""
    return json.dumps(manifest, separators=(",", ":"), ensure_ascii=True) + "\n"


def sig_is_current(file: str, gpg_key_id: str) -> bool:
    """True when the embedded signature is current and verifies for its payload."""
    try:
        with open(file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    sig = data.get("signature")
    if not sig:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".asc", delete=False) as tmp:
        tmp.write(sig + "\n")
        tmp_path = tmp.name
    try:
        out = subprocess.run(["gpg", "--list-packets", tmp_path],
                             capture_output=True, text=True).stdout
        m = re.search(r"issuer key ID ([A-Fa-f0-9]{16})", out)
        if not m or m.group(1).upper() != (gpg_key_id or "").upper():
            return False
        verify = subprocess.run(
            ["gpg", "--batch", "--verify", tmp_path, "-"],
            input=_signing_payload(data["manifest"]), capture_output=True, text=True,
        )
        return verify.returncode == 0
    finally:
        os.unlink(tmp_path)


def sign_manifest(file: str, gpg_key_id: str, passphrase: Optional[str]) -> bool:
    """Sign the ``.manifest`` payload and embed the armored signature. False on failure."""
    if not gpg_key_id:
        return True
    with open(file, encoding="utf-8") as fh:
        data = json.load(fh)
    payload = _signing_payload(data["manifest"])
    args = ["gpg", "--batch", "--yes", "--armor", "--detach-sign",
            "--local-user", gpg_key_id, "--output", "-"]
    if passphrase:
        args += ["--passphrase", passphrase, "--pinentry-mode", "loopback"]
    proc = subprocess.run(args, input=payload, capture_output=True, text=True)
    sig = proc.stdout.rstrip("\n")  # command-substitution parity: no trailing newline
    if proc.returncode != 0 or not sig:
        return False
    data["signature"] = sig
    with open(file, "w", encoding="utf-8") as fh:
        fh.write(jsonio.dumps_formatted(data))
    return True


# ---- GPG key setup + full generation orchestrator ---------------------------
def import_gpg_key(private_key: str) -> tuple[str, bool]:
    """Import the armored key and return (key_id, signing_failed).

    Empty ``private_key`` -> ("", False) (signing disabled, not a failure).
    """
    from ..core import actions
    if not private_key:
        actions.log("GPG_PRIVATE_KEY not set - signatures will be skipped.")
        return "", False
    subprocess.run(["gpg", "--batch", "--import"], input=private_key,
                   capture_output=True, text=True)
    out = subprocess.run(["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
                         capture_output=True, text=True).stdout
    key_id = ""
    for line in out.splitlines():
        if line.startswith("sec"):
            parts = line.split()
            if len(parts) >= 2 and "/" in parts[1]:
                key_id = parts[1].split("/", 1)[1]
                break
    if key_id:
        actions.log(f"GPG signing enabled (key: {key_id})")
        return key_id, False
    actions.warning("GPG key import succeeded but no usable secret key found - signatures will be skipped.")
    return "", True


def _canonical(version: str) -> str:
    return re.sub(r"-[0-9]+$", "", version)


ICON_EXTS = ("png", "svg", "jpg", "webp")


def _sync_icon(plugin_dir: str, plugin_name: str) -> None:
    """Copy the first supported source logo beside the plugin metadata."""
    import shutil

    for ext in ICON_EXTS:
        source = os.path.join(plugin_dir, f"logo.{ext}")
        if os.path.isfile(source):
            shutil.copy(source, f"metadata/{plugin_name}/logo.{ext}")
            return


def strip_signatures() -> None:
    """Remove ``.signature`` from every manifest (no key configured or signing failed)."""
    import glob as _glob
    for f in _glob.glob("metadata/*/manifest.json") + ["manifest.json"]:
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if "signature" in data:
            del data["signature"]
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(jsonio.dumps_formatted(data))


def generate(source_branch: str, releases_branch: str, repository: str,
             build_meta_dir: str) -> int:
    """Full generate-manifest.sh: per-plugin manifests, root manifest, signing."""
    import glob
    from ..core import actions, gh

    generated_at = now_iso()
    registry_url = f"https://github.com/{repository}"
    registry_name = repository
    download_base_url = f"https://github.com/{repository}/releases/download"
    raw_releases_url = f"https://raw.githubusercontent.com/{repository}/{releases_branch}"
    metadata_base_url = ""
    if feature_flags.SPLIT_MANIFEST_BASE_URLS:
        metadata_base_url = gh.pages_url(repository).rstrip("/") or raw_releases_url

    key_id, signing_failed = import_gpg_key(os.environ.get("GPG_PRIVATE_KEY", ""))
    passphrase = os.environ.get("GPG_PASSPHRASE") or None

    def maybe_sign(path: str) -> None:
        nonlocal signing_failed
        if not sign_manifest(path, key_id, passphrase):
            actions.warning(f"GPG signing failed for {path} - all signatures will be removed.")
            signing_failed = True

    def sign_if_needed(path: str, written: bool) -> None:
        if written:
            maybe_sign(path)
        elif key_id and not signing_failed and not sig_is_current(path, key_id):
            maybe_sign(path)

    releases = gh.release_list(repository)
    release_download_counts = (
        gh.release_download_counts(repository)
        if feature_flags.MANIFEST_DOWNLOAD_TOTALS else {}
    )
    root_entries: list[dict] = []
    plugin_count = 0
    changelog_numbers: dict[str, Optional[str]] = {}

    for plugin_dir in sorted(glob.glob("plugins/*/")):
        plugin_file = os.path.join(plugin_dir, "plugin.json")
        if not os.path.isfile(plugin_file):
            continue
        plugin_name = os.path.basename(plugin_dir.rstrip("/"))
        plugin_key = plugin_name.replace("-", "_")
        with open(plugin_file, encoding="utf-8") as fh:
            raw = json.load(fh)
        current_version = str(raw.get("version"))
        min_da = effective_min_dispatcharr_version(plugin_dir, raw)
        max_da = str(raw.get("max_dispatcharr_version") or "")
        unlisted = raw.get("unlisted") is True
        ai_assisted_disclosed = (
            feature_flags.AI_ASSISTED_MANIFEST_DISCLOSURE and
            (raw.get("ai_assisted") is True or
             ai_assisted.has_attribution(source_branch, plugin_name))
        )
        actions.log(f"  {plugin_name}")

        existing_manifest_file = f"metadata/{plugin_name}/manifest.json"
        os.makedirs(f"metadata/{plugin_name}", exist_ok=True)
        if feature_flags.SPLIT_MANIFEST_BASE_URLS:
            _sync_icon(plugin_dir, plugin_name)
        existing_manifest = None
        if os.path.isfile(existing_manifest_file):
            try:
                with open(existing_manifest_file, encoding="utf-8") as fh:
                    existing_manifest = json.load(fh)
            except ValueError:
                existing_manifest = None

        prefix = f"{plugin_name}-"
        stable_tags = [str(release["tag"]) for release in releases
                       if str(release["tag"]).startswith(prefix) and not release.get("prerelease")]
        prerelease_tags = [str(release["tag"]) for release in releases
                           if str(release["tag"]).startswith(prefix) and release.get("prerelease")]
        tags = versioned_tags(stable_tags, plugin_name) + sorted(prerelease_tags)

        versioned_zips: list[dict] = []
        latest_metadata: dict = {}
        latest_zip_version = ""
        latest_size_kb = 0
        latest_size_set = False
        plugin_download_count = 0
        latest_download_count = None

        for release_tag in tags:
            zip_version = release_tag[len(prefix):]
            zip_url = f"{plugin_name}-{zip_version}/{plugin_name}-{zip_version}.zip"
            canonical_version = _canonical(zip_version)
            download_count = (
                release_download_counts.get(release_tag, 0)
                if feature_flags.MANIFEST_DOWNLOAD_TOTALS else None
            )
            if download_count is not None:
                plugin_download_count += download_count

            metadata: dict = {}
            fresh = os.path.join(build_meta_dir, plugin_key, f"{plugin_key}-{canonical_version}.json")
            if build_meta_dir and os.path.isfile(fresh):
                with open(fresh, encoding="utf-8") as fh:
                    metadata = json.load(fh)
            elif existing_manifest is not None:
                for entry in ((existing_manifest.get("manifest") or {}).get("versions") or []):
                    if entry.get("version") == canonical_version:
                        metadata = entry
                        break

            if release_tag in prerelease_tags:
                metadata = {**metadata, "prerelease": True}

            commit_sha = str(metadata.get("commit_sha") or "")
            if metadata and "changelog" not in metadata and commit_sha:
                if commit_sha not in changelog_numbers:
                    changelog_numbers[commit_sha] = gh.commit_pull_number(repository, commit_sha)[0]
                changelog = changelog_numbers[commit_sha]
                if changelog:
                    metadata = {**metadata, "changelog": changelog}

            zip_size_kb = 0
            if metadata:
                zip_size_kb = metadata.get("size_kb", metadata.get("size", 0)) or 0
            if release_tag not in prerelease_tags and not latest_size_set:
                latest_size_kb = zip_size_kb
                latest_size_set = True

            versioned_zips.append(build_version_entry(
                metadata, zip_url, zip_size_kb, canonical_version, download_count))
            if metadata and release_tag not in prerelease_tags and not latest_metadata:
                latest_metadata = metadata
                latest_zip_version = zip_version
                latest_download_count = download_count

        latest_url = ""
        if latest_zip_version:
            latest_url = f"{plugin_name}-{latest_zip_version}/{plugin_name}-{latest_zip_version}.zip"

        versioned_zips = override_current_min_max(versioned_zips, current_version, min_da, max_da)

        plugin_entry = build_plugin_entry(raw, plugin_name, latest_url, registry_url,
                                           registry_name, versioned_zips, latest_metadata,
                                            latest_size_kb, ai_assisted_disclosed,
                                            (plugin_download_count
                                             if feature_flags.MANIFEST_DOWNLOAD_TOTALS else None),
                                            latest_download_count, min_da, max_da)
        written = write_manifest_if_changed(existing_manifest_file, plugin_entry, generated_at)
        sign_if_needed(existing_manifest_file, written)

        if unlisted:
            continue

        manifest_url = (f"metadata/{plugin_name}/manifest.json"
                        if feature_flags.SPLIT_MANIFEST_BASE_URLS
                        else f"{raw_releases_url}/metadata/{plugin_name}/manifest.json")
        root_entries.append(build_root_entry(raw, plugin_name, latest_metadata,
                                               latest_size_kb, min_da, max_da,
                                               latest_url, manifest_url,
                                               ai_assisted_disclosed,
                                               (plugin_download_count
                                                if feature_flags.MANIFEST_DOWNLOAD_TOTALS else None)))
        plugin_count += 1

    try:
        registry_messages = messages.load_active(now=datetime.datetime.now(datetime.timezone.utc))
    except messages.FeedError as exc:
        actions.error(f"Registry messages are invalid: {exc}")
        return 1

    inner_root = build_root_manifest(
        registry_url, registry_name, download_base_url, root_entries,
        metadata_base_url if feature_flags.SPLIT_MANIFEST_BASE_URLS else None,
        registry_messages)
    written = write_manifest_if_changed("manifest.json", inner_root, generated_at)
    sign_if_needed("manifest.json", written)

    if signing_failed or not key_id:
        actions.warning("Removing all manifest signatures (no GPG key configured or signing failed).")
        strip_signatures()

    actions.log(f"Generated manifest.json with {plugin_count} plugin(s).")
    return 0
