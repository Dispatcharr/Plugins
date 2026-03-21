#!/bin/bash
set -e

# publish-releases-readme.sh
# Generates the root README.md for the releases branch.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

# Format an ISO8601 timestamp as "Mon DD, HH:MM UTC"
fmt_date() { date -d "$1" -u +"%b %d %Y, %H:%M UTC" 2>/dev/null || echo "$1"; }

# Render a full plugin block (used in second pass)
render_plugin() {
  local is_deprecated=$1
  local plugin_name=$2
  local name=$3
  local version=$4
  local author=$5
  local description=$6
  local maintainers=$7
  local last_updated=$8
  local commit_sha=$9
  local commit_sha_short=${10}
  local version_count=${11}
  local license=${12}

  local zip_url="https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/zips/${plugin_name}/${plugin_name}-latest.zip"
  local source_url="https://github.com/${GITHUB_REPOSITORY}/tree/$SOURCE_BRANCH/plugins/${plugin_name}"
  local readme_url="https://github.com/${GITHUB_REPOSITORY}/blob/$SOURCE_BRANCH/plugins/${plugin_name}/README.md"
  local releases_readme_url="https://github.com/${GITHUB_REPOSITORY}/blob/$RELEASES_BRANCH/zips/${plugin_name}/README.md"
  local commit_url="https://github.com/${GITHUB_REPOSITORY}/commit/${commit_sha}"
  local releases_dir="./zips/${plugin_name}"
  local has_source_readme=false
  [[ -f "plugins/$plugin_name/README.md" ]] && has_source_readme=true

  local suffix=""
  [[ "$is_deprecated" == "true" ]] && suffix=" (deprecated)"

  echo "### [$name]($releases_readme_url)$suffix"
  echo ""
  echo "**Version:** \`$version\` | **Author:** $author | **Last Updated:** $(fmt_date "$last_updated")"
  echo ""
  echo "$description"
  echo ""
  if [[ -n "$license" ]]; then
    echo "**License:** [$license](https://spdx.org/licenses/${license}.html)"
    echo ""
  fi
  echo "**Downloads:**"
  echo "- [Latest Release (\`$version\`)]($zip_url)"
  echo "- [All Versions ($version_count available)]($releases_dir)"
  echo ""

  local footer=""
  [[ -n "$maintainers" ]] && footer="**Maintainers:** $maintainers | "
  footer+="**Source:** [Browse](${source_url})"
  [[ "$has_source_readme" == "true" ]] && footer+=" | [README]($readme_url)"
  footer+=" | **Last Change:** [\`$commit_sha_short\`]($commit_url)"
  echo "$footer"
  echo ""
  echo "---"
  echo ""
}

{
  echo "# Plugin Releases"
  echo ""
  echo "This branch contains all published plugin releases."
  echo ""
  echo "## Quick Access"
  echo ""
  echo "- [manifest.json](./manifest.json) - Complete plugin registry with metadata"
  echo "- [zips/](./zips/) - Plugin ZIP files and per-plugin manifests"
  echo ""
  echo "## Available Plugins"
  echo ""
  echo "| Plugin | Version | Author | License | Description |"
  echo "|--------|---------|-------|---------|-------------|"

  # Table rows: active plugins first, then deprecated
  for pass in active deprecated; do
    for plugin_dir in plugins/*/; do
      plugin_file="$plugin_dir/plugin.json"
      [[ ! -f "$plugin_file" ]] && continue
      deprecated=$(jq -r '.deprecated // false' "$plugin_file")
      unlisted=$(jq -r '.unlisted // false' "$plugin_file")
      [[ "$unlisted" == "true" ]] && continue
      [[ "$pass" == "active" && "$deprecated" == "true" ]] && continue
      [[ "$pass" == "deprecated" && "$deprecated" != "true" ]] && continue

      plugin_name=$(basename "$plugin_dir")
      name=$(jq -r '.name' "$plugin_file")
      version=$(jq -r '.version' "$plugin_file")
      author=$(jq -r '.author // ""' "$plugin_file")
      description=$(jq -r '.description' "$plugin_file")
      table_license=$(jq -r '.license // "-"' "$plugin_file")
      anchor=$(echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g')
      suffix=""
      [[ "$pass" == "deprecated" ]] && suffix=" (deprecated)"
      license_cell="${table_license}"

      echo "| [\`$name\`](#$anchor)$suffix | \`$version\` | $author | $license_cell | $description |"
    done
  done

  echo ""
  echo "---"
  echo ""

  # Detailed sections: active plugins
  for plugin_dir in plugins/*/; do
    plugin_file="$plugin_dir/plugin.json"
    [[ ! -f "$plugin_file" ]] && continue
    deprecated=$(jq -r '.deprecated // false' "$plugin_file")
    unlisted=$(jq -r '.unlisted // false' "$plugin_file")
    [[ "$deprecated" == "true" ]] && continue
    [[ "$unlisted" == "true" ]] && continue

    plugin_name=$(basename "$plugin_dir")
    name=$(jq -r '.name' "$plugin_file")
    version=$(jq -r '.version' "$plugin_file")
    author=$(jq -r '.author // ""' "$plugin_file")
    description=$(jq -r '.description' "$plugin_file")
    maintainers=$(jq -r '[.maintainers[]?] | join(", ")' "$plugin_file")
    last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
      || date -u +"%Y-%m-%dT%H:%M:%SZ")
    commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null || echo "unknown")
    commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null || echo "unknown")
    version_count=$(ls -1 "zips/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
      | grep -v latest | wc -l | tr -d ' ')
    plugin_license=$(jq -r '.license // ""' "$plugin_file")

    render_plugin "false" "$plugin_name" "$name" "$version" "$author" "$description" \
      "$maintainers" "$last_updated" "$commit_sha" "$commit_sha_short" "$version_count" "$plugin_license"
  done

  # Deprecated section (only if any exist)
  has_deprecated=false
  for plugin_dir in plugins/*/; do
    plugin_file="$plugin_dir/plugin.json"
    [[ ! -f "$plugin_file" ]] && continue
    if [[ "$(jq -r '.deprecated // false' "$plugin_file")" == "true" ]]; then
      has_deprecated=true
      break
    fi
  done

  if [[ "$has_deprecated" == "true" ]]; then
    echo ""
    echo "## Deprecated Plugins"
    echo ""
    echo "These plugins are deprecated and may be removed in the future."
    echo ""

    for plugin_dir in plugins/*/; do
      plugin_file="$plugin_dir/plugin.json"
      [[ ! -f "$plugin_file" ]] && continue
      deprecated=$(jq -r '.deprecated // false' "$plugin_file")
      unlisted=$(jq -r '.unlisted // false' "$plugin_file")
      [[ "$deprecated" != "true" ]] && continue
      [[ "$unlisted" == "true" ]] && continue

      plugin_name=$(basename "$plugin_dir")
      name=$(jq -r '.name' "$plugin_file")
      version=$(jq -r '.version' "$plugin_file")
      author=$(jq -r '.author // ""' "$plugin_file")
      description=$(jq -r '.description' "$plugin_file")
      maintainers=$(jq -r '[.maintainers[]?] | join(", ")' "$plugin_file")
      last_updated=$(git log -1 --format=%cI origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null \
        || date -u +"%Y-%m-%dT%H:%M:%SZ")
      commit_sha=$(git log -1 --format=%H origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null || echo "unknown")
      commit_sha_short=$(git log -1 --format=%h origin/$SOURCE_BRANCH -- "$plugin_dir" 2>/dev/null || echo "unknown")
      version_count=$(ls -1 "zips/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
        | grep -v latest | wc -l | tr -d ' ')
      plugin_license=$(jq -r '.license // ""' "$plugin_file")

      render_plugin "true" "$plugin_name" "$name" "$version" "$author" "$description" \
        "$maintainers" "$last_updated" "$commit_sha" "$commit_sha_short" "$version_count" "$plugin_license"
    done
  fi

  echo "## Using the Manifest"
  echo ""
  echo "Fetch \`manifest.json\` to programmatically access plugin metadata and download URLs:"
  echo ""
  echo "\`\`\`bash"
  echo "curl https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/$RELEASES_BRANCH/manifest.json"
  echo "\`\`\`"
  echo ""
  echo "---"
  echo ""
  echo "*Last updated: $(date -u +"%b %d %Y, %H:%M UTC")*"
} > README.md
