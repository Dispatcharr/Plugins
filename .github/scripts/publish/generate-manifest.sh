#!/bin/bash
set -e

# publish-generate-manifest.sh
# Generates metadata/<plugin>/manifest.json for each plugin and the root manifest.json.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
repo_url="https://github.com/${GITHUB_REPOSITORY}"
repo_name="${GITHUB_REPOSITORY##*/}"

# GPG signing setup - optional; set GPG_PRIVATE_KEY (armored) and optionally GPG_PASSPHRASE
gpg_key_id=""
gpg_signing_failed=0
if [[ -n "${GPG_PRIVATE_KEY:-}" ]]; then
  echo "$GPG_PRIVATE_KEY" | gpg --batch --import 2>/dev/null
  gpg_key_id=$(gpg --list-secret-keys --keyid-format LONG 2>/dev/null \
    | awk '/^sec/{print $2}' | head -1 | cut -d'/' -f2)
  if [[ -n "$gpg_key_id" ]]; then
    echo "GPG signing enabled (key: $gpg_key_id)"
  else
    echo "::warning::GPG key import succeeded but no usable secret key found - signatures will be skipped."
    gpg_signing_failed=1
  fi
else
  echo "GPG_PRIVATE_KEY not set - signatures will be skipped."
fi

# Writes $2 (JSON string) to $1 only when the content (excluding generated_at)
# differs from the file already on disk.  Returns 0 if written, 1 if skipped.
write_manifest_if_changed() {
  local dest="$1" new_content="$2"
  if [[ -f "$dest" ]]; then
    local existing_stripped new_stripped
    existing_stripped=$(jq -c 'del(.generated_at)' "$dest")
    new_stripped=$(echo "$new_content" | jq -c 'del(.generated_at)')
    if [[ "$existing_stripped" == "$new_stripped" ]]; then
      return 1
    fi
  fi
  echo "$new_content" > "$dest"
  return 0
}

# Returns 0 if $1.sig exists and was created by the current gpg_key_id, 1 otherwise.
# Used to detect key rotation: if the key changed we must re-sign even when content is unchanged.
sig_is_current() {
  local file="$1"
  [[ -f "${file}.sig" ]] || return 1
  local sig_fpr
  sig_fpr=$(jq -c '.' "$file" | gpg --verify --status-fd 1 "${file}.sig" - 2>/dev/null \
    | awk '/VALIDSIG/{print $3}' | head -1)
  # gpg_key_id is a 16-char long key ID; VALIDSIG gives the full 40-char fingerprint
  [[ -n "$sig_fpr" && "$sig_fpr" == *"$gpg_key_id" ]] && return 0 || return 1
}

# Signs $1 (a JSON file) and writes an armored detached signature to $1.sig.
# Sets gpg_signing_failed=1 on any gpg error so all sigs are cleaned up at the end.
sign_manifest() {
  local file="$1"
  [[ -z "$gpg_key_id" ]] && return 0
  local gpg_opts=(--batch --yes --armor --detach-sign --local-user "$gpg_key_id" --output "${file}.sig")
  if [[ -n "${GPG_PASSPHRASE:-}" ]]; then
    gpg_opts+=(--passphrase "$GPG_PASSPHRASE" --pinentry-mode loopback)
  fi
  if ! jq -c '.' "$file" | gpg "${gpg_opts[@]}" 2>/dev/null; then
    echo "::warning::GPG signing failed for ${file} - all signatures will be removed."
    gpg_signing_failed=1
    rm -f "${file}.sig"
  fi
}

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

  new_plugin_manifest=$(echo "$plugin_entry" | jq \
    --arg ts "$generated_at" \
    --arg repo_url "$repo_url" \
    --arg repo_name "$repo_name" \
    '{generated_at: $ts, repo_url: $repo_url, repo_name: $repo_name} + .')
  if write_manifest_if_changed "metadata/$plugin_name/manifest.json" "$new_plugin_manifest"; then
    sign_manifest "metadata/$plugin_name/manifest.json"
  elif [[ -n "$gpg_key_id" ]] && ! sig_is_current "metadata/$plugin_name/manifest.json"; then
    sign_manifest "metadata/$plugin_name/manifest.json"
  fi
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

new_root_manifest=$(
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
  } | jq \
    --arg ts "$generated_at" \
    --arg repo_url "$repo_url" \
    --arg repo_name "$repo_name" \
    '{generated_at: $ts, repo_url: $repo_url, repo_name: $repo_name} + .'
)
if write_manifest_if_changed "manifest.json" "$new_root_manifest"; then
  sign_manifest "manifest.json"
elif [[ -n "$gpg_key_id" ]] && ! sig_is_current "manifest.json"; then
  sign_manifest "manifest.json"
fi

# If any signing step failed, remove ALL .sig files so the repo is never
# left in a partially-signed state.
if [[ "$gpg_signing_failed" -eq 1 ]]; then
  echo "::warning::Removing all .sig files due to signing failure."
  find metadata -name "*.sig" -delete 2>/dev/null || true
  rm -f manifest.json.sig
fi

echo "Generated manifest.json with ${#root_entries[@]} plugin(s)."
