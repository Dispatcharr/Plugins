#!/bin/bash
set -e

# publish-per-plugin-readmes.sh
# Generates metadata/<plugin>/README.md for every plugin.
# Version/metadata discovery is driven by the per-plugin manifest.json written
# by generate-manifest.sh (which runs before this script). No local ZIPs required.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

# Format an ISO8601 timestamp as "Mon DD, HH:MM UTC"
fmt_date() { date -d "$1" -u +"%b %d %Y, %H:%M UTC" 2>/dev/null || echo "$1"; }

# Encode a string for use in a shields.io badge path segment
# spaces -> _, underscores -> __, hyphens -> --
shields_encode() {
  local s="$1"
  s="${s//_/__}"
  s="${s//-/--}"
  s="${s// /_}"
  printf '%s' "$s"
}

# Read root_url from the root manifest (set by generate-manifest.sh)
root_url=$(jq -r '.manifest.root_url // ""' "manifest.json" 2>/dev/null || echo "")

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_file="$plugin_dir/plugin.json"
  [[ ! -f "$plugin_file" ]] && continue

  manifest_file="metadata/$plugin_name/manifest.json"
  if [[ ! -f "$manifest_file" ]]; then
    echo "  $plugin_name (no manifest, skipping README)"
    continue
  fi

  name=$(jq -r '.name' "$plugin_file")
  description=$(jq -r '.description' "$plugin_file")
  author=$(jq -r '.author // ""' "$plugin_file")
  maintainers=$(jq -r '[.maintainers[]?] | join(", ")' "$plugin_file")
  repo_url=$(jq -r '.repo_url // empty' "$plugin_file")
  discord_thread=$(jq -r '.discord_thread // empty' "$plugin_file")
  license=$(jq -r '.license // ""' "$plugin_file")
  min_dispatcharr=$(jq -r '.min_dispatcharr_version // empty' "$plugin_file")
  max_dispatcharr=$(jq -r '.max_dispatcharr_version // empty' "$plugin_file")
  version=$(jq -r '.version' "$plugin_file")
  last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
    || date -u +"%Y-%m-%dT%H:%M:%SZ")
  has_readme=false
  [[ -f "$plugin_dir/README.md" ]] && has_readme=true

  # Read latest metadata from manifest
  latest_url_path=$(jq -r '.manifest.latest.latest_url // empty' "$manifest_file")
  latest_full_url=""
  [[ -n "$root_url" && -n "$latest_url_path" ]] && latest_full_url="${root_url}/${latest_url_path}"

  {
    echo "[Back to All Plugins](../../README.md)"
    echo ""
    echo "# $name"
    echo ""
    echo "**Version:** \`$version\` | **Author:** $author | **Last Updated:** $(fmt_date "$last_updated")"
    echo ""
    echo "$description"
    echo ""
    # Build badge row
    local_discord_link="$discord_thread"
    badges=""
    if [[ -n "$license" ]]; then
      badges="[![License: $license](https://img.shields.io/badge/License-$(shields_encode "$license")-blue?style=flat-square)](https://spdx.org/licenses/${license}.html)"
    fi
    if [[ -n "$local_discord_link" ]]; then
      [[ -n "$badges" ]] && badges+=" "
      badges+="[![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)]($local_discord_link)"
    fi
    if [[ -n "$repo_url" ]]; then
      [[ -n "$badges" ]] && badges+=" "
      badges+="[![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)]($repo_url)"
    fi
    if [[ -n "$badges" ]]; then
      echo "$badges"
      echo ""
    fi
    if [[ -n "$min_dispatcharr" || -n "$max_dispatcharr" ]]; then
      compat_badges=""
      if [[ -n "$min_dispatcharr" ]]; then
        compat_badges="![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-$(shields_encode "$min_dispatcharr")-brightgreen?style=flat-square)"
      fi
      if [[ -n "$max_dispatcharr" ]]; then
        [[ -n "$compat_badges" ]] && compat_badges+=" "
        compat_badges+="![Dispatcharr max](https://img.shields.io/badge/Dispatcharr_max-$(shields_encode "$max_dispatcharr")-orange?style=flat-square)"
      fi
      echo "$compat_badges"
      echo ""
    fi
    echo "## Downloads"
    echo ""
    echo "### Latest Release"
    echo ""

    if [[ -n "$latest_full_url" ]]; then
      latest_build_timestamp=$(jq -r '.manifest.latest.build_timestamp // empty' "$manifest_file")
      latest_commit_sha=$(jq -r '.manifest.latest.commit_sha // empty' "$manifest_file")
      latest_commit_sha_short=$(jq -r '.manifest.latest.commit_sha_short // empty' "$manifest_file")
      latest_md5=$(jq -r '.manifest.latest.checksum_md5 // empty' "$manifest_file")
      latest_sha256=$(jq -r '.manifest.latest.checksum_sha256 // empty' "$manifest_file")

      echo "- **Download:** [\`${plugin_name}-latest.zip\`](${latest_full_url})"
      [[ -n "$latest_build_timestamp" ]] && echo "- **Built:** $(fmt_date "$latest_build_timestamp")"
      [[ -n "$latest_commit_sha" ]] && echo "- **Source Commit:** [\`$latest_commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${latest_commit_sha})"
      if [[ -n "$latest_md5" || -n "$latest_sha256" ]]; then
        echo ""
        echo "**Checksums:**"
        echo "\`\`\`"
        [[ -n "$latest_md5" ]]    && echo "MD5:    $latest_md5"
        [[ -n "$latest_sha256" ]] && echo "SHA256: $latest_sha256"
        echo "\`\`\`"
      fi
    fi

    echo ""
    echo "### All Versions"
    echo ""
    echo "| Version | Download | Built | Commit | MD5 | SHA256 |"
    echo "|---------|----------|-------|--------|-----|--------|"

    while IFS= read -r version_json; do
      ver=$(echo "$version_json" | jq -r '.version // empty')
      [[ -z "$ver" ]] && continue
      url_path=$(echo "$version_json" | jq -r '.url // empty')
      full_url=""
      [[ -n "$root_url" && -n "$url_path" ]] && full_url="${root_url}/${url_path}"
      commit_sha=$(echo "$version_json" | jq -r '.commit_sha // empty')
      commit_sha_short=$(echo "$version_json" | jq -r '.commit_sha_short // empty')
      build_timestamp=$(echo "$version_json" | jq -r '.build_timestamp // empty')
      checksum_md5=$(echo "$version_json" | jq -r '.checksum_md5 // empty')
      checksum_sha256=$(echo "$version_json" | jq -r '.checksum_sha256 // empty')
      build_date=$(fmt_date "$build_timestamp")
      commit_cell="-"
      [[ -n "$commit_sha" ]] && commit_cell="[\`$commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha})"
      download_cell="-"
      [[ -n "$full_url" ]] && download_cell="[Download](${full_url})"
      echo "| \`$ver\` | $download_cell | ${build_date:--} | $commit_cell | ${checksum_md5:--} | ${checksum_sha256:--} |"
    done < <(jq -c '.manifest.versions[]?' "$manifest_file" 2>/dev/null)

    echo ""
    echo "---"
    echo ""
    local_footer=""
    [[ -n "$maintainers" ]] && local_footer="**Maintainers:** $maintainers | "
    local_footer+="**Source:** [Browse Plugin](https://github.com/${GITHUB_REPOSITORY}/tree/$SOURCE_BRANCH/plugins/${plugin_name})"
    echo "$local_footer"
    echo ""
    echo "**Metadata:** [View full manifest](./manifest.json)"

    if [[ "$has_readme" == "true" ]]; then
      echo ""
      echo "---"
      echo ""
      echo "## Plugin README"
      echo ""
      cat "$plugin_dir/README.md"
    fi
  } > "metadata/$plugin_name/README.md"

  echo "  $plugin_name"
done
