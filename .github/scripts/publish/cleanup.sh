#!/bin/bash
set -e

# publish-cleanup.sh
# Removes release artifacts for plugins that no longer exist in source,
# prunes versioned ZIPs beyond MAX_VERSIONED_ZIPS, and removes orphaned files.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH
# Optional env: MAX_VERSIONED_ZIPS (default: 10)

: "${SOURCE_BRANCH:?}"
MAX_VERSIONED_ZIPS=${MAX_VERSIONED_ZIPS:-10}

# Remove artifacts for deleted plugins
if [[ -d releases ]]; then
  for release_dir in releases/*/; do
    [[ ! -d "$release_dir" ]] && continue
    plugin_name=$(basename "$release_dir")
    if [[ ! -d "plugins/$plugin_name" ]]; then
      echo "  Removing deleted plugin: $plugin_name"
      rm -rf "$release_dir" "metadata/$plugin_name"
    fi
  done
fi

# Prune old versions and orphans per plugin
for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  zip_dir="releases/$plugin_name"
  metadata_dir="metadata/$plugin_name"

  # Remove oldest ZIPs beyond the limit
  while IFS= read -r old_zip; do
    version=$(basename "$old_zip" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
    rm -f "$old_zip" "$metadata_dir/${plugin_name}-${version}.json"
    echo "  Removed $plugin_name v$version (over limit)"
  done < <(ls -1t "$zip_dir/${plugin_name}-"*.zip 2>/dev/null \
    | grep -v "${plugin_name}-latest.zip" \
    | awk "NR>$MAX_VERSIONED_ZIPS")

  # Remove orphaned ZIPs with no matching metadata
  for zipfile in "$zip_dir/${plugin_name}-"*.zip; do
    [[ ! -f "$zipfile" ]] && continue
    zip_basename=$(basename "$zipfile")
    [[ "$zip_basename" == "${plugin_name}-latest.zip" ]] && continue
    version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
    if [[ ! -f "$metadata_dir/${plugin_name}-${version}.json" ]]; then
      rm -f "$zipfile"
      echo "  Removed orphaned ZIP: $zip_basename"
    fi
  done

  # Remove orphaned metadata with no matching ZIP
  for metafile in "$metadata_dir/${plugin_name}-"*.json; do
    [[ ! -f "$metafile" ]] && continue
    version=$(basename "$metafile" | sed "s/${plugin_name}-\(.*\)\.json/\1/")
    if [[ ! -f "$zip_dir/${plugin_name}-${version}.zip" ]]; then
      rm -f "$metafile"
      echo "  Removed orphaned metadata: $(basename "$metafile")"
    fi
  done
done
