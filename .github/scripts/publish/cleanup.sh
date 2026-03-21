#!/bin/bash
set -e

# publish-cleanup.sh
# Removes release artifacts for plugins that no longer exist in source,
# and prunes versioned ZIPs beyond MAX_VERSIONED_ZIPS.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH
# Optional env: MAX_VERSIONED_ZIPS (default: 10)

: "${SOURCE_BRANCH:?}"
MAX_VERSIONED_ZIPS=${MAX_VERSIONED_ZIPS:-10}

# Remove artifacts for deleted plugins
if [[ -d zips ]]; then
  for release_dir in zips/*/; do
    [[ ! -d "$release_dir" ]] && continue
    plugin_name=$(basename "$release_dir")
    if [[ ! -d "plugins/$plugin_name" ]]; then
      echo "  Removing deleted plugin: $plugin_name"
      rm -rf "$release_dir"
    fi
  done
fi

# Prune old versions per plugin
for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  zip_dir="zips/$plugin_name"

  # Remove oldest ZIPs beyond the limit
  while IFS= read -r old_zip; do
    echo "  Removed $plugin_name $(basename "$old_zip") (over limit)"
    rm -f "$old_zip"
  done < <(ls -1t "$zip_dir/${plugin_name}-"*.zip 2>/dev/null \
    | grep -v "${plugin_name}-latest.zip" \
    | awk "NR>$MAX_VERSIONED_ZIPS")
done
