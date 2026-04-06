#!/bin/bash
set -e

# publish-generate-manifest.sh
# Generates zips/<plugin>/manifest.json for each plugin and the root manifest.json.
#
# Called from the releases branch checkout directory by publish-plugins.sh.
# Required env: SOURCE_BRANCH, RELEASES_BRANCH, GITHUB_REPOSITORY

: "${SOURCE_BRANCH:?}" "${RELEASES_BRANCH:?}" "${GITHUB_REPOSITORY:?}"

generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
registry_url="https://github.com/${GITHUB_REPOSITORY}"
registry_name="${GITHUB_REPOSITORY}"
root_url="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/${RELEASES_BRANCH}"

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

# Writes a manifest wrapper to $1 with $2 as the signed payload (.manifest),
# only when .manifest content differs from what is on disk.
# Wrapper structure: {generated_at, manifest: <payload>}
# The .signature field is added separately by sign_manifest.
# Returns 0 if written, 1 if skipped (content unchanged).
write_manifest_if_changed() {
  local dest="$1" manifest_payload="$2"
  local new_compact
  new_compact=$(echo "$manifest_payload" | jq -c '.')
  if [[ -f "$dest" ]]; then
    local existing_manifest
    existing_manifest=$(jq -c '.manifest' "$dest" 2>/dev/null)
    if [[ "$existing_manifest" == "$new_compact" ]]; then
      return 1
    fi
  fi
  jq -n \
    --arg generated_at "$generated_at" \
    --argjson manifest "$new_compact" \
    '{generated_at: $generated_at, manifest: $manifest}' \
    > "$dest"
  return 0
}

# Returns 0 if the manifest at $1 has an embedded .signature made by the current
# gpg_key_id, 1 otherwise. Uses --list-packets on a temp file to read the issuer
# key ID without cryptographic verification, avoiding trust-level pitfalls.
sig_is_current() {
  local file="$1"
  local sig
  sig=$(jq -r '.signature // empty' "$file" 2>/dev/null)
  [[ -n "$sig" ]] || return 1
  local tmp_sig sig_key_id
  tmp_sig=$(mktemp)
  printf '%s\n' "$sig" > "$tmp_sig"
  sig_key_id=$(gpg --list-packets "$tmp_sig" 2>/dev/null \
    | sed -n 's/.*issuer key ID \([A-Fa-f0-9]\{16\}\).*/\1/p' | head -1 \
    | tr 'a-f' 'A-F')
  rm -f "$tmp_sig"
  local cur_key_upper
  cur_key_upper=$(echo "$gpg_key_id" | tr 'a-f' 'A-F')
  [[ -n "$sig_key_id" && "$sig_key_id" == "$cur_key_upper" ]]
}

# Signs the .manifest payload of $1 and embeds the armored signature as .signature
# in the same JSON file. Sets gpg_signing_failed=1 on any error.
sign_manifest() {
  local file="$1"
  [[ -z "$gpg_key_id" ]] && return 0
  local gpg_opts=(--batch --yes --armor --detach-sign --local-user "$gpg_key_id" --output -)
  if [[ -n "${GPG_PASSPHRASE:-}" ]]; then
    gpg_opts+=(--passphrase "$GPG_PASSPHRASE" --pinentry-mode loopback)
  fi
  local sig
  sig=$(jq -c '.manifest' "$file" | gpg "${gpg_opts[@]}" 2>/dev/null) || true
  if [[ -z "$sig" ]]; then
    echo "::warning::GPG signing failed for ${file} - all signatures will be removed."
    gpg_signing_failed=1
    return 1
  fi
  local tmp
  tmp=$(mktemp)
  if jq --arg sig "$sig" '. + {signature: $sig}' "$file" > "$tmp"; then
    mv "$tmp" "$file"
  else
    rm -f "$tmp"
    echo "::warning::Failed to embed signature in ${file}."
    gpg_signing_failed=1
  fi
}

plugin_entries=()
root_entries=()

for plugin_dir in plugins/*/; do
  plugin_file="$plugin_dir/plugin.json"
  [[ ! -f "$plugin_file" ]] && continue
  plugin_name=$(basename "$plugin_dir")
  plugin_key=${plugin_name//-/_}
  unlisted=false
  [[ "$(jq -r '.unlisted // false' "$plugin_file")" == "true" ]] && unlisted=true

  echo "  $plugin_name"

  latest_url="zips/${plugin_name}/${plugin_name}-latest.zip"

  versioned_zips="[]"
  latest_metadata="{}"

  # existing per-plugin manifest from previous run - used as metadata fallback
  existing_manifest_file="zips/$plugin_name/manifest.json"

  while IFS= read -r zipfile; do
    zip_basename=$(basename "$zipfile")
    zip_version=$(echo "$zip_basename" | sed "s/${plugin_name}-\(.*\)\.zip/\1/")
    zip_url="zips/${plugin_name}/${zip_basename}"

    # Fresh metadata from this run takes priority; fall back to existing manifest
    fresh_meta_file="${BUILD_META_DIR:-}/$plugin_key/${plugin_key}-${zip_version}.json"
    metadata="{}"
    if [[ -n "${BUILD_META_DIR:-}" && -f "$fresh_meta_file" ]]; then
      metadata=$(cat "$fresh_meta_file")
    elif [[ -f "$existing_manifest_file" ]]; then
      meta_from_manifest=$(jq -c --arg v "$zip_version" \
        '.manifest.versions[]? | select(.version == $v)' "$existing_manifest_file" 2>/dev/null || true)
      [[ -n "$meta_from_manifest" ]] && metadata="$meta_from_manifest"
    fi

    if [[ "$metadata" != "{}" ]]; then
      versioned_zips=$(jq --arg url "$zip_url" --argjson metadata "$metadata" \
        '. + [($metadata + {url: $url})]' <<< "$versioned_zips")
      if [[ "$latest_metadata" == "{}" ]]; then
        latest_metadata="$metadata"
      fi
    else
      versioned_zips=$(jq --arg version "$zip_version" --arg url "$zip_url" \
        '. + [{version: $version, url: $url}]' <<< "$versioned_zips")
    fi
  done < <(ls -1 "zips/$plugin_name/${plugin_name}"-*.zip 2>/dev/null \
      | grep -v latest | sort -t- -k2 -V -r)

  plugin_entry=$(jq \
    --arg plugin_name "$plugin_name" \
    --arg latest_url "$latest_url" \
    --arg registry_url "$registry_url" \
    --arg registry_name "$registry_name" \
    --argjson versioned_zips "$versioned_zips" \
    --argjson latest_metadata "$latest_metadata" \
    'with_entries(select(.key | IN(
      "name","description","author","maintainers",
      "deprecated","repo_url","discord_thread","license"
    ))) + {
      slug: $plugin_name,
      registry_url: $registry_url,
      registry_name: $registry_name,
      versions: $versioned_zips
    } + (
      if ($latest_metadata | length > 0) then {
        last_updated: $latest_metadata.last_updated,
        latest: ($latest_metadata + {
          latest_url: $latest_url,
          url: $versioned_zips[0].url
        })
      } else {} end
    )' \
    "$plugin_file")

  if write_manifest_if_changed "zips/$plugin_name/manifest.json" "$plugin_entry"; then
    sign_manifest "zips/$plugin_name/manifest.json"
  elif [[ -n "$gpg_key_id" && "$gpg_signing_failed" -eq 0 ]] && ! sig_is_current "zips/$plugin_name/manifest.json"; then
    sign_manifest "zips/$plugin_name/manifest.json"
  fi
  plugin_entries+=("$plugin_entry")

  # Unlisted plugins get a per-plugin manifest but are excluded from the root manifest
  [[ "$unlisted" == "true" ]] && continue

  # Compact root manifest entry
  desc_raw=$(jq -r '.description // ""' "$plugin_file")
  if [[ ${#desc_raw} -gt 200 ]]; then
    desc_trimmed="${desc_raw:0:197}..."
  else
    desc_trimmed="$desc_raw"
  fi

  plugin_manifest_url="zips/${plugin_name}/manifest.json"

  root_entry=$(jq -n \
    --argjson latest_metadata "$latest_metadata" \
    --argjson versioned_zips "$versioned_zips" \
    --arg slug "$plugin_name" \
    --arg name "$(jq -r '.name // ""' "$plugin_file")" \
    --arg description "$desc_trimmed" \
    --arg manifest_url "$plugin_manifest_url" \
    --arg author "$(jq -r '.author // ""' "$plugin_file")" \
    --arg license "$(jq -r '.license // ""' "$plugin_file")" \
    --argjson deprecated "$(jq 'if .deprecated == true then true else null end' "$plugin_file")" \
    '{
      slug: $slug,
      name: $name,
      description: $description,
      manifest_url: $manifest_url,
      author: $author,
      license: (if $license != "" then $license else null end),
      deprecated: $deprecated,
      last_updated: ($latest_metadata.last_updated // null),
      latest_version: ($latest_metadata.version // null),
      latest_md5: ($latest_metadata.checksum_md5 // null),
      latest_sha256: ($latest_metadata.checksum_sha256 // null),
      latest_url: ($versioned_zips[0].url // null),
      min_dispatcharr_version: ($latest_metadata.min_dispatcharr_version // null),
      max_dispatcharr_version: ($latest_metadata.max_dispatcharr_version // null)
    } | with_entries(select(.value != null))')
  root_entries+=("$root_entry")
done

inner_root=$(
  {
    echo '{'
    echo '  "registry_url": '"$(jq -n --arg u "$registry_url" '$u')"','
    echo '  "registry_name": '"$(jq -n --arg u "$registry_name" '$u')"','
    echo '  "root_url": '"$(jq -n --arg u "$root_url" '$u')"','
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
  } | jq -c '.'
)
if write_manifest_if_changed "manifest.json" "$inner_root"; then
  sign_manifest "manifest.json"
elif [[ -n "$gpg_key_id" && "$gpg_signing_failed" -eq 0 ]] && ! sig_is_current "manifest.json"; then
  sign_manifest "manifest.json"
fi

# If any signing step failed, or no GPG key is configured, strip embedded
# signatures from all manifests so the repo is never left in a partially-signed
# or stale-signed state (e.g. incremental runs where unchanged manifests retain
# signatures from a previous key that is no longer present).
if [[ "$gpg_signing_failed" -eq 1 ]] || [[ -z "$gpg_key_id" ]]; then
  echo "::warning::Removing all manifest signatures (no GPG key configured or signing failed)."
  while IFS= read -r -d '' _f; do
    _tmp=$(mktemp)
    jq 'del(.signature)' "$_f" > "$_tmp" && mv "$_tmp" "$_f" || rm -f "$_tmp"
  done < <(find zips -name "manifest.json" -print0 2>/dev/null)
  _tmp=$(mktemp)
  jq 'del(.signature)' manifest.json > "$_tmp" && mv "$_tmp" manifest.json || rm -f "$_tmp"
  unset _f _tmp
fi

echo "Generated manifest.json with ${#root_entries[@]} plugin(s)."
