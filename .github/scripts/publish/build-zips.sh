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

  echo "  $plugin_name v$version - building"
  echo "$plugin_name@$version" >> changed_plugins.txt

  commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir")
  commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir")
  build_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
    || date -u +"%Y-%m-%dT%H:%M:%SZ")

  zip -r "$zip_path" "$plugin_dir" -q

  checksum_md5=$(md5sum "$zip_path" | awk '{print $1}')
  checksum_sha256=$(shasum -a 256 "$zip_path" | awk '{print $1}')

  min_da_version=$(jq -r '.min_dispatcharr_version // ""' "$plugin_dir/plugin.json")
  max_da_version=$(jq -r '.max_dispatcharr_version // ""' "$plugin_dir/plugin.json")

  mkdir -p "$BUILD_META_DIR/$plugin_name"
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
    '{
      version: $version,
      commit_sha: $commit_sha,
      commit_sha_short: $commit_sha_short,
      build_timestamp: $build_timestamp,
      last_updated: $last_updated,
      checksum_md5: $checksum_md5,
      checksum_sha256: $checksum_sha256
    } + (if $min_da_version != "" then {min_dispatcharr_version: $min_da_version} else {} end)
      + (if $max_da_version != "" then {max_dispatcharr_version: $max_da_version} else {} end)' \
    > "$BUILD_META_DIR/$plugin_name/${plugin_name}-${version}.json"

  cp "$zip_path" "zips/$plugin_name/${plugin_name}-latest.zip"
done

changed=$(wc -l < changed_plugins.txt | tr -d ' ')
echo "Built $changed new/updated plugin(s)."
