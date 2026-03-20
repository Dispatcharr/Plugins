#!/bin/bash
set -e

# publish-build-zips.sh
# Builds versioned ZIPs and per-version metadata files for all plugins.
# Skips plugins whose current version already has a ZIP + metadata file.
# Writes changed_plugins.txt to cwd (one "name@version" per line).
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

> changed_plugins.txt

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  version=$(jq -r '.version' "$plugin_dir/plugin.json")

  mkdir -p "releases/$plugin_name" "metadata/$plugin_name"

  zip_path="releases/$plugin_name/${plugin_name}-${version}.zip"
  metadata_path="metadata/$plugin_name/${plugin_name}-${version}.json"

  if [[ -f "$zip_path" ]] && [[ -f "$metadata_path" ]]; then
    echo "  $plugin_name v$version - skipping (already exists)"
    continue
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
    > "$metadata_path"

  cp "$zip_path" "releases/$plugin_name/${plugin_name}-latest.zip"
done

changed=$(wc -l < changed_plugins.txt | tr -d ' ')
echo "Built $changed new/updated plugin(s)."
