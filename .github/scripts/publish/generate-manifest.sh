#!/bin/bash
set -e

# publish-generate-manifest.sh
# Generates metadata/<plugin>/manifest.json for each plugin and the root manifest.json.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

plugin_entries=()
root_entries=()

for plugin_dir in plugins/*/; do
  plugin_file="$plugin_dir/plugin.json"
  [[ ! -f "$plugin_file" ]] && continue
  plugin_name=$(basename "$plugin_dir")

  echo "  $plugin_name"

  latest_url="https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${plugin_name}-latest.zip"

  versioned_zips="[]"
  latest_metadata="{}"

  while IFS= read -r zipfile; do
    zip_basename=$(basename "$zipfile")
    zip_version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
    zip_url="https://github.com/${GITHUB_REPOSITORY}/raw/$RELEASES_BRANCH/releases/${plugin_name}/${zip_basename}"
    metadata_file="metadata/$plugin_name/${plugin_name}-${zip_version}.json"

    if [[ -f "$metadata_file" ]]; then
      metadata=$(cat "$metadata_file")
      versioned_zips=$(jq --arg url "$zip_url" --argjson metadata "$metadata" \
        '. + [($metadata + {url: $url})]' <<< "$versioned_zips")
      if [[ "$latest_metadata" == "{}" ]]; then
        latest_metadata="$metadata"
      fi
    else
      versioned_zips=$(jq --arg version "$zip_version" --arg url "$zip_url" \
        '. + [{version: $version, url: $url}]' <<< "$versioned_zips")
    fi
  done < <(ls -1 "releases/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
      | grep -v latest | sort -t- -k2 -V -r)

  # Compute icon_url before building plugin_entry so it can be included in both manifests
  icon_url=""
  if [[ -f "plugins/$plugin_name/logo.png" ]]; then
    icon_url="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/${SOURCE_BRANCH}/plugins/${plugin_name}/logo.png"
  fi

  plugin_entry=$(jq \
    --arg plugin_name "$plugin_name" \
    --arg latest_url "$latest_url" \
    --arg icon_url "$icon_url" \
    --argjson versioned_zips "$versioned_zips" \
    --argjson latest_metadata "$latest_metadata" \
    'with_entries(select(.key | IN(
      "name","version","description","author","maintainers",
      "deprecated","unlisted","min_dispatcharr_version","max_dispatcharr_version","repo_url","discord_thread","license"
    ))) + {
      slug: $plugin_name,
      latest_url: $latest_url,
      versions: $versioned_zips
    } + (if $icon_url != "" then {icon_url: $icon_url} else {} end)
      + (
      if ($latest_metadata | length > 0) then {
        last_updated: $latest_metadata.last_updated,
        latest: ($latest_metadata + {
          latest_url: $latest_url,
          url: $versioned_zips[0].url
        }),
        latest_commit_sha: $latest_metadata.commit_sha,
        latest_commit_sha_short: $latest_metadata.commit_sha_short,
        latest_build_timestamp: $latest_metadata.build_timestamp,
        latest_checksum_md5: $latest_metadata.checksum_md5,
        latest_checksum_sha256: $latest_metadata.checksum_sha256
      } else {} end
    )' \
    "$plugin_file")

  echo "$plugin_entry" | jq '.' > "metadata/$plugin_name/manifest.json"
  plugin_entries+=("$plugin_entry")

  # Compact root manifest entry
  desc_raw=$(jq -r '.description // ""' "$plugin_file")
  if [[ ${#desc_raw} -gt 200 ]]; then
    desc_trimmed="${desc_raw:0:197}..."
  else
    desc_trimmed="$desc_raw"
  fi

  plugin_manifest_url="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/${RELEASES_BRANCH}/metadata/${plugin_name}/manifest.json"

  root_entry=$(jq -n \
    --argjson latest_metadata "$latest_metadata" \
    --arg name "$(jq -r '.name // ""' "$plugin_file")" \
    --arg description "$desc_trimmed" \
    --arg icon_url "$icon_url" \
    --arg manifest_url "$plugin_manifest_url" \
    --arg author "$(jq -r '.author // ""' "$plugin_file")" \
    --arg license "$(jq -r '.license // ""' "$plugin_file")" \
    --arg latest_url "$latest_url" \
    '{
      name: $name,
      description: $description,
      icon_url: (if $icon_url != "" then $icon_url else null end),
      manifest_url: $manifest_url,
      author: $author,
      license: (if $license != "" then $license else null end),
      latest_version: ($latest_metadata.version // null),
      latest_md5: ($latest_metadata.checksum_md5 // null),
      latest_url: $latest_url,
      min_dispatcharr_version: ($latest_metadata.min_dispatcharr_version // null),
      max_dispatcharr_version: ($latest_metadata.max_dispatcharr_version // null)
    } | with_entries(select(.value != null))')
  root_entries+=("$root_entry")
done

{
  echo '{'
  echo '  "plugins": ['
  first=true
  for entry in "${root_entries[@]}"; do
    if [[ "$first" != true ]]; then echo ","; fi
    first=false
    echo "$entry" | sed 's/^/    /'
  done
  echo ""
  echo '  ]'
  echo '}'
} | jq --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" '{generated_at: $ts} + .' > manifest.json

echo "Generated manifest.json with ${#root_entries[@]} plugin(s)."
