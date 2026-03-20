#!/bin/bash
set -e

# publish-per-plugin-readmes.sh
# Generates releases/<plugin>/README.md for every plugin.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

# Format an ISO8601 timestamp as "Mon DD, HH:MM UTC"
fmt_date() { date -d "$1" -u +"%b %d %Y, %H:%M UTC" 2>/dev/null || echo "$1"; }

for plugin_dir in plugins/*/; do
  [[ ! -d "$plugin_dir" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_file="$plugin_dir/plugin.json"
  [[ ! -f "$plugin_file" ]] && continue

  name=$(jq -r '.name' "$plugin_file")
  description=$(jq -r '.description' "$plugin_file")
  author=$(jq -r '.author // ""' "$plugin_file")
  repo_url=$(jq -r '.repo_url // empty' "$plugin_file")
  discord_thread=$(jq -r '.discord_thread // empty' "$plugin_file")
  license=$(jq -r '.license // ""' "$plugin_file")
  has_readme=false
  [[ -f "$plugin_dir/README.md" ]] && has_readme=true

  {
    echo "[Back to All Plugins](../../README.md)"
    echo ""
    echo "# $name"
    echo ""
    echo "$description"
    echo ""
    echo "**Author:** $author"
    echo ""
    if [[ -n "$repo_url" ]]; then
      echo "**Repository:** [$repo_url]($repo_url)"
      echo ""
    fi
    if [[ -n "$discord_thread" ]]; then
      echo "**Discord:** [Discussion Thread]($discord_thread)"
      echo ""
    fi
    if [[ -n "$license" ]]; then
      echo "**License:** [$license](https://spdx.org/licenses/${license}.html)"
      echo ""
    fi
    echo "## Downloads"
    echo ""
    echo "### Latest Release"
    echo ""

    latest_zip="releases/$plugin_name/${plugin_name}-latest.zip"
    if [[ -f "$latest_zip" ]]; then
      latest_versioned=$(ls -1 "releases/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
        | grep -v latest | sort -t- -k2 -V -r | head -1)
      if [[ -n "$latest_versioned" ]]; then
        zip_basename=$(basename "$latest_versioned")
        latest_version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
        metadata_file="metadata/$plugin_name/${plugin_name}-${latest_version}.json"

        echo "**Version:** \`$latest_version\`"
        echo ""

        if [[ -f "$metadata_file" ]]; then
          commit_sha=$(jq -r '.commit_sha' "$metadata_file")
          commit_sha_short=$(jq -r '.commit_sha_short' "$metadata_file")
          build_timestamp=$(jq -r '.build_timestamp' "$metadata_file")
          checksum_md5=$(jq -r '.checksum_md5' "$metadata_file")
          checksum_sha256=$(jq -r '.checksum_sha256' "$metadata_file")

          echo "- **Download:** [\`${plugin_name}-latest.zip\`](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${plugin_name}-latest.zip)"
          echo "- **Built:** $(fmt_date "$build_timestamp")"
          echo "- **Source Commit:** [\`$commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha})"
          echo ""
          echo "**Checksums:**"
          echo "\`\`\`"
          echo "MD5:    $checksum_md5"
          echo "SHA256: $checksum_sha256"
          echo "\`\`\`"
        else
          echo "- **Download:** [\`${plugin_name}-latest.zip\`](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${plugin_name}-latest.zip)"
        fi
      fi
    fi

    echo ""
    echo "### All Versions"
    echo ""
    echo "| Version | Download | Built | Commit | MD5 Checksum |"
    echo "|---------|----------|-------|--------|--------------|"

    while IFS= read -r zipfile; do
      zip_basename=$(basename "$zipfile")
      version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
      metadata_file="metadata/$plugin_name/${plugin_name}-${version}.json"

      if [[ -f "$metadata_file" ]]; then
        commit_sha_short=$(jq -r '.commit_sha_short' "$metadata_file")
        commit_sha=$(jq -r '.commit_sha' "$metadata_file")
        build_timestamp=$(jq -r '.build_timestamp' "$metadata_file")
        checksum_md5=$(jq -r '.checksum_md5' "$metadata_file")
        build_date=$(fmt_date "$build_timestamp")
        echo "| \`$version\` | [Download](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${zip_basename}) | $build_date | [\`$commit_sha_short\`](https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha}) | \`$checksum_md5\` |"
      else
        echo "| \`$version\` | [Download](https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${zip_basename}) | - | - | - |"
      fi
    done < <(ls -1 "releases/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
        | grep -v latest | sort -t- -k2 -V -r)

    echo ""
    echo "---"
    echo ""
    echo "**Source:** [Browse Plugin](https://github.com/${GITHUB_REPOSITORY}/tree/$SOURCE_BRANCH/plugins/${plugin_name})"
    echo ""
    echo "**Metadata:** [View full metadata](../../metadata/${plugin_name}/manifest.json)"

    if [[ "$has_readme" == "true" ]]; then
      echo ""
      echo "---"
      echo ""
      echo "## Plugin README"
      echo ""
      cat "$plugin_dir/README.md"
    fi
  } > "releases/$plugin_name/README.md"

  echo "  $plugin_name"
done
