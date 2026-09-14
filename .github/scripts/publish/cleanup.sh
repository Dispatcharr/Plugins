#!/bin/bash
set -e

# publish-cleanup.sh
# Removes GitHub Releases for plugins that no longer exist in source,
# and prunes versioned releases beyond MAX_VERSIONED_ZIPS.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, GITHUB_REPOSITORY, GITHUB_TOKEN
# Optional env: MAX_VERSIONED_ZIPS (default: 10)

: "${SOURCE_BRANCH:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_TOKEN:?}"
MAX_VERSIONED_ZIPS=${MAX_VERSIONED_ZIPS:-10}

# Fetch all release tags once to avoid repeated API calls
all_tags=$(gh release list --repo "$GITHUB_REPOSITORY" --json tagName --limit 500 \
  | jq -r '.[].tagName')

# Remove releases for deleted plugins
if [[ -d zips ]]; then
  for release_dir in metadata/*/; do
    [[ ! -d "$release_dir" ]] && continue
    plugin_name=$(basename "$release_dir")
    if [[ ! -d "plugins/$plugin_name" ]]; then
      echo "  Removing deleted plugin releases: $plugin_name"
      echo "$all_tags" | grep "^${plugin_name}-" | while IFS= read -r tag; do
        echo "    Deleting release $tag"
        gh release delete "$tag" --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag 2>/dev/null || true
      done
      rm -rf "$release_dir"
    fi
  done
fi

# Prune old versioned releases per plugin (keep MAX_VERSIONED_ZIPS most recent)
for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")

  # Get versioned tags for this plugin (exclude -latest), sorted newest-first by semver
  versioned_tags=$(echo "$all_tags" \
    | grep "^${plugin_name}-" \
    | grep -v "^${plugin_name}-latest$" \
    | sed "s/^${plugin_name}-//" \
    | sort -V -r \
    | sed "s/^/${plugin_name}-/")

  tag_count=$(echo "$versioned_tags" | grep -c . || true)
  if (( tag_count <= MAX_VERSIONED_ZIPS )); then
    continue
  fi

  # Delete tags beyond the limit
  echo "$versioned_tags" | awk "NR>$MAX_VERSIONED_ZIPS" | while IFS= read -r old_tag; do
    echo "  Removed release $old_tag (over limit of $MAX_VERSIONED_ZIPS)"
    gh release delete "$old_tag" --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag 2>/dev/null || true
  done
done
