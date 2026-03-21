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
    echo "**Source:** [Browse Plugin](https://github.com/${GITHUB_REPOSITORY}/tree/$SOURCE_BRANCH/plugins/${plugin_name})"
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
