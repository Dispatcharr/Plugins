#!/bin/bash
set -e

# publish-build-zips.sh
# Builds versioned ZIPs and per-version metadata for all plugins.
# Per-version metadata is written to a temporary working directory (BUILD_META_DIR)
# so generate-manifest.sh can consume it within this CI run without persisting
# per-version JSON files to the releases branch.
# Skips plugins whose current version already has a ZIP and an entry in the
# existing per-plugin manifest.
# Writes changed_plugins.txt to cwd (one "name@version" per line).
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}" "${BUILD_META_DIR:?}"

> changed_plugins.txt

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_key=${plugin_name//-/_}
  version=$(jq -r '.version' "$plugin_dir/plugin.json")

  mkdir -p "zips/$plugin_name"

  zip_path="zips/$plugin_name/${plugin_name}-${version}.zip"
  existing_manifest="zips/$plugin_name/manifest.json"

  # Skip if ZIP exists and the version is already in the existing manifest
  if [[ -f "$zip_path" ]]; then
    if [[ -f "$existing_manifest" ]] && \
       jq -e --arg v "$version" '.manifest.versions[]? | select(.version == $v)' "$existing_manifest" >/dev/null 2>&1; then
      echo "  $plugin_name v$version - skipping (already exists)"
      continue
    fi
  fi

  source_type=$(jq -r '.source_type // "local"' "$plugin_dir/plugin.json")
  build_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [[ "$source_type" == "external" ]]; then
    source_url_template=$(jq -r '.source_url' "$plugin_dir/plugin.json")
    source_url_resolved="${source_url_template//\{version\}/$version}"
    echo "  $plugin_name v$version - fetching external ZIP from $source_url_resolved"
    echo "$plugin_key@$version" >> changed_plugins.txt
    curl -fsSL "$source_url_resolved" -o "$zip_path" || {
      echo "::error::Failed to download external ZIP from $source_url_resolved"
      exit 1
    }
    commit_sha=""
    commit_sha_short=""
    last_updated="$build_timestamp"
  else
    echo "  $plugin_name v$version - building"
    echo "$plugin_key@$version" >> changed_plugins.txt
    commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir")
    commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir")
    last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
      || date -u +"%Y-%m-%dT%H:%M:%SZ")
    source_url_resolved=""
    (
      abspath="$(pwd)/$zip_path"
      tmpdir=$(mktemp -d)
      trap 'rm -rf "$tmpdir"' EXIT
      cp -r "plugins/$plugin_name" "$tmpdir/$plugin_key"
      cd "$tmpdir" && zip -r "$abspath" "$plugin_key" -q
    )
  fi

  checksum_md5=$(md5sum "$zip_path" | awk '{print $1}')
  checksum_sha256=$(shasum -a 256 "$zip_path" | awk '{print $1}')

  min_da_version=$(jq -r '.min_dispatcharr_version // ""' "$plugin_dir/plugin.json")
  max_da_version=$(jq -r '.max_dispatcharr_version // ""' "$plugin_dir/plugin.json")

  mkdir -p "$BUILD_META_DIR/$plugin_key"
  jq -n \
    --arg version "$version" \
    --arg commit_sha "$commit_sha" \
    --arg commit_sha_short "$commit_sha_short" \
    --arg build_timestamp "$build_timestamp" \
    --arg last_updated "$last_updated" \
    --arg checksum_md5 "$checksum_md5" \
    --arg checksum_sha256 "$checksum_sha256" \
    --arg min_da_version "$min_da_version" \
    --arg max_da_version "$max_da_version" \
    --arg source_url "$source_url_resolved" \
    '{      version: $version,
      commit_sha: (if $commit_sha != "" then $commit_sha else null end),
      commit_sha_short: (if $commit_sha_short != "" then $commit_sha_short else null end),
      build_timestamp: $build_timestamp,
      last_updated: $last_updated,
      checksum_md5: $checksum_md5,
      checksum_sha256: $checksum_sha256,
      min_dispatcharr_version: (if $min_da_version != "" then $min_da_version else null end),
      max_dispatcharr_version: (if $max_da_version != "" then $max_da_version else null end),
      source_url: (if $source_url != "" then $source_url else null end)
    } | with_entries(select(.value != null))' \
    > "$BUILD_META_DIR/$plugin_key/${plugin_key}-${version}.json"

  cp "$zip_path" "zips/$plugin_name/${plugin_name}-latest.zip"
done

changed=$(wc -l < changed_plugins.txt | tr -d ' ')
echo "Built $changed new/updated plugin(s)."
