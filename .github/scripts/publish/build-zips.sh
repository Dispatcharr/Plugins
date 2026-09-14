#!/bin/bash
set -e

# publish-build-zips.sh
# Builds versioned ZIPs and per-version metadata for all plugins.
# Per-version metadata is written to a temporary working directory (BUILD_META_DIR)
# so generate-manifest.sh can consume it within this CI run without persisting
# per-version JSON files to the releases branch.
# Skips plugins whose current version already has a GitHub Release tag.
# Uploads each new ZIP to GitHub Releases (versioned tag + -latest alias tag).
# Writes changed_plugins.txt to cwd (one "name@version" per line).
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY, GITHUB_TOKEN

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}" "${BUILD_META_DIR:?}" "${GITHUB_TOKEN:?}"

> changed_plugins.txt

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_key=${plugin_name//-/_}
  version=$(jq -r '.version' "$plugin_dir/plugin.json")

  mkdir -p "metadata/$plugin_name"

  zip_path="/tmp/${plugin_name}-${version}.zip"
  existing_manifest="metadata/$plugin_name/manifest.json"
  release_tag="${plugin_name}-${version}"

  # Skip if a GitHub Release already exists for this version.
  # The release is the source of truth; the manifest is regenerated from it.
  if gh release view "$release_tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
    echo "  $plugin_name v$version - skipping (release already exists)"
    continue
  fi

  source_type=$(jq -r '.source_type // "local"' "$plugin_dir/plugin.json")
  build_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [[ "$source_type" == "external" ]]; then
    source_url_template=$(jq -r '.source_url' "$plugin_dir/plugin.json")
    source_url_resolved="${source_url_template//\{version\}/$version}"
    echo "  $plugin_name v$version - fetching external ZIP from $source_url_resolved"
    echo "$plugin_key@$version" >> changed_plugins.txt
    download_ok=false
    for attempt in 1 2 3; do
      if curl -fsSL "$source_url_resolved" -o "$zip_path"; then
        download_ok=true
        break
      fi
      rm -f "$zip_path"
      if [[ "$attempt" -lt 3 ]]; then
        echo "  Download attempt $attempt failed, retrying in 15s..."
        sleep 15
      fi
    done
    if [[ "$download_ok" != "true" ]]; then
      echo "::error::Failed to download external ZIP from $source_url_resolved after 3 attempts"
      exit 1
    fi
    commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir")
    commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir")
    last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
      || date -u +"%Y-%m-%dT%H:%M:%SZ")
  else
    echo "  $plugin_name v$version - building"
    echo "$plugin_key@$version" >> changed_plugins.txt
    commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir")
    commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir")
    last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
      || date -u +"%Y-%m-%dT%H:%M:%SZ")
    source_url_resolved=""
    (
      tmpdir=$(mktemp -d)
      trap 'rm -rf "$tmpdir"' EXIT
      cp -r "plugins/$plugin_name" "$tmpdir/$plugin_key"
      cd "$tmpdir" && zip -r "$zip_path" "$plugin_key" -q
    )
  fi

  checksum_md5=$(md5sum "$zip_path" | awk '{print $1}')
  checksum_sha256=$(shasum -a 256 "$zip_path" | awk '{print $1}')

  min_da_version=$(jq -r '.min_dispatcharr_version // ""' "$plugin_dir/plugin.json")
  max_da_version=$(jq -r '.max_dispatcharr_version // ""' "$plugin_dir/plugin.json")

  zip_size_bytes=$(stat -f%z "$zip_path" 2>/dev/null || stat -c%s "$zip_path" 2>/dev/null || echo 0)
  zip_size_kb=$(( zip_size_bytes / 1024 ))

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
    --argjson size_kb "$zip_size_kb" \
    '{
      version: $version,
      commit_sha: (if $commit_sha != "" then $commit_sha else null end),
      commit_sha_short: (if $commit_sha_short != "" then $commit_sha_short else null end),
      build_timestamp: $build_timestamp,
      last_updated: $last_updated,
      checksum_md5: $checksum_md5,
      checksum_sha256: $checksum_sha256,
      min_dispatcharr_version: (if $min_da_version != "" then $min_da_version else null end),
      max_dispatcharr_version: (if $max_da_version != "" then $max_da_version else null end),
      source_url: (if $source_url != "" then $source_url else null end),
      size_kb: $size_kb
    } | with_entries(select(.value != null))' \
    > "$BUILD_META_DIR/$plugin_key/${plugin_key}-${version}.json"

  # Build release notes
  readme_url="https://github.com/${GITHUB_REPOSITORY}/blob/releases/metadata/${plugin_name}/README.md"
  release_notes=""
  if [[ -n "$commit_sha" ]]; then
    commit_url="https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha}"
    release_notes="**Commit:** [\`${commit_sha_short}\`](${commit_url})"
    pr_info=$(gh api "repos/${GITHUB_REPOSITORY}/commits/${commit_sha}/pulls" \
      --jq '.[0] | {number: .number, url: .html_url}' 2>/dev/null || echo '{}')
    pr_number=$(echo "$pr_info" | jq -r '.number // empty')
    pr_url=$(echo "$pr_info" | jq -r '.url // empty')
    if [[ -n "$pr_number" && "$pr_number" != "null" ]]; then
      release_notes+=$'\n'"**PR:** [#${pr_number}](${pr_url})"
    fi
    release_notes+=$'\n'
  fi
  release_notes+="**README:** [Plugin README](${readme_url})"

  # Upload versioned GitHub Release
  echo "  $plugin_name v$version - uploading to GitHub Releases"
  gh release create "$release_tag" \
    --repo "$GITHUB_REPOSITORY" \
    --title "${plugin_name} v${version}" \
    --notes "$release_notes" \
    "$zip_path"

  rm -f "$zip_path"
done

changed=$(wc -l < changed_plugins.txt | tr -d ' ')
echo "Built $changed new/updated plugin(s)."
