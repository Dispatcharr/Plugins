#!/bin/bash
set -e

# publish-per-plugin-readmes.sh
# Generates zips/<plugin>/README.md for every plugin.
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

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_file="$plugin_dir/plugin.json"
  [[ ! -f "$plugin_file" ]] && continue

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

    latest_zip="zips/$plugin_name/${plugin_name}-latest.zip"
    if [[ -f "$latest_zip" ]]; then
      latest_versioned=$(ls -1 "zips/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
        | grep -v latest | sort -t- -k2 -V -r | head -1)
      if [[ -n "$latest_versioned" ]]; then
        zip_basename=$(basename "$latest_versioned")
        latest_version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
        manifest_file="zips/$plugin_name/manifest.json"
        meta_entry=""
        if [[ -f "$manifest_file" ]]; then
          meta_entry=$(jq -c --arg v "$latest_version" \
            '.manifest.versions[]? | select(.version == $v)' "$manifest_file" 2>/dev/null || true)
        fi
        if [[ -n "$meta_entry" ]]; then
          commit_sha=$(echo "$meta_entry" | jq -r '.commit_sha // empty')
          commit_sha_short=$(echo "$meta_entry" | jq -r '.commit_sha_short // empty')
          build_timestamp=$(echo "$meta_entry" | jq -r '.build_timestamp // empty')
          checksum_md5=$(echo "$meta_entry" | jq -r '.checksum_md5 // empty')
          checksum_sha256=$(echo "$meta_entry" | jq -r '.checksum_sha256 // empty')

          echo "- **Download:** [\`${plugin_name}-latest.zip\`](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/zips/${plugin_name}/${plugin_name}-latest.zip)"
          [[ -n "$build_timestamp" ]] && echo "- **Built:** $(fmt_date "$build_timestamp")"
          [[ -n "$commit_sha" ]] && echo "- **Source Commit:** [\`$commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha})"
          if [[ -n "$checksum_md5" || -n "$checksum_sha256" ]]; then
            echo ""
            echo "**Checksums:**"
            echo "\`\`\`"
            [[ -n "$checksum_md5" ]]    && echo "MD5:    $checksum_md5"
            [[ -n "$checksum_sha256" ]] && echo "SHA256: $checksum_sha256"
            echo "\`\`\`"
          fi
        else
          echo "- **Download:** [\`${plugin_name}-latest.zip\`](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/zips/${plugin_name}/${plugin_name}-latest.zip)"
        fi
      fi
    fi

    echo ""
    echo "### All Versions"
    echo ""
    echo "| Version | Download | Built | Commit | MD5 | SHA256 |"
    echo "|---------|----------|-------|--------|-----|--------|"

    manifest_file="zips/$plugin_name/manifest.json"
    while IFS= read -r zipfile; do
      zip_basename=$(basename "$zipfile")
      version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")

      meta_entry=""
      if [[ -f "$manifest_file" ]]; then
        meta_entry=$(jq -c --arg v "$version" \
          '.manifest.versions[]? | select(.version == $v)' "$manifest_file" 2>/dev/null || true)
      fi

      if [[ -n "$meta_entry" ]]; then
        commit_sha_short=$(echo "$meta_entry" | jq -r '.commit_sha_short // empty')
        commit_sha=$(echo "$meta_entry" | jq -r '.commit_sha // empty')
        build_timestamp=$(echo "$meta_entry" | jq -r '.build_timestamp // empty')
        checksum_md5=$(echo "$meta_entry" | jq -r '.checksum_md5 // empty')
        checksum_sha256=$(echo "$meta_entry" | jq -r '.checksum_sha256 // empty')
        build_date=$(fmt_date "$build_timestamp")
        commit_cell="-"
        [[ -n "$commit_sha" ]] && commit_cell="[\`$commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha})"
        echo "| \`$version\` | [Download](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/zips/${plugin_name}/${zip_basename}) | ${build_date:--} | $commit_cell | ${checksum_md5:--} | ${checksum_sha256:--} |"
      else
        echo "| \`$version\` | [Download](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/zips/${plugin_name}/${zip_basename}) | - | - | - |"
      fi
    done < <(ls -1 "zips/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
        | grep -v latest | sort -t- -k2 -V -r)

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
  } > "zips/$plugin_name/README.md"

  echo "  $plugin_name"
done
