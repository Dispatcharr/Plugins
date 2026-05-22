#!/bin/bash
set -e

# validate-single-plugin.sh
# Validates one plugin and writes a markdown report fragment to a file.
#
# Usage: validate-single-plugin.sh <plugin_name> <pr_author> <base_ref> <output_file>
#
# Arguments:
#   plugin_name  - Plugin folder name (e.g. my-plugin)
#   pr_author    - GitHub username of PR author
#   base_ref     - Base branch reference (e.g. main)
#   output_file  - File path to write the markdown report fragment to
#
# Outputs (written to $GITHUB_OUTPUT):
#   result       - "pass" or "fail"
#   is_new       - "true" if this is a new plugin (not on base branch)
#   has_permission - "true" if pr_author is permitted to modify this plugin
#
# Environment variables required:
#   GITHUB_REPOSITORY - Full repository name (owner/repo)
#   GH_TOKEN          - GitHub token for API access

PLUGIN_NAME=$1
PR_AUTHOR=$2
BASE_REF=$3
OUTPUT_FILE=${4:-/dev/stdout}

if [[ -z "$PLUGIN_NAME" || -z "$PR_AUTHOR" || -z "$BASE_REF" ]]; then
  echo "Usage: $0 <plugin_name> <pr_author> <base_ref> [output_file]"
  exit 1
fi

REPO_OWNER=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f1)
REPO_NAME=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f2)

PLUGIN_DIR="plugins/$PLUGIN_NAME"
PLUGIN_JSON="$PLUGIN_DIR/plugin.json"
README="$PLUGIN_DIR/README.md"

check_repo_maintainer() {
  local author=$1
  PERMISSION=$(gh api repos/$REPO_OWNER/$REPO_NAME/collaborators/$author/permission --jq .permission 2>/dev/null || echo "none")
  if [[ "$PERMISSION" == "admin" || "$PERMISSION" == "maintain" || "$PERMISSION" == "write" ]]; then
    echo "1"
  else
    echo "0"
  fi
}

validate_semver() {
  local version=$1
  if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo "1"; else echo "0"; fi
}

validate_dispatcharr_version() {
  local version=$1
  if [[ "$version" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo "1"; else echo "0"; fi
}

version_greater_than() {
  local new_version=$1
  local old_version=$2
  IFS='.' read -r NEW_MAJOR NEW_MINOR NEW_PATCH <<< "$new_version"
  IFS='.' read -r OLD_MAJOR OLD_MINOR OLD_PATCH <<< "$old_version"
  if (( NEW_MAJOR > OLD_MAJOR )); then return 0; fi
  if (( NEW_MAJOR < OLD_MAJOR )); then return 1; fi
  if (( NEW_MINOR > OLD_MINOR )); then return 0; fi
  if (( NEW_MINOR < OLD_MINOR )); then return 1; fi
  if (( NEW_PATCH > OLD_PATCH )); then return 0; fi
  return 1
}

failed=0
is_new="false"
has_permission="false"

{
  echo "### Plugin: \`$PLUGIN_NAME\`"
  echo ""
  # Show description and repo link as header subtext if plugin.json is readable
  if [[ -f "$PLUGIN_JSON" ]]; then
    _desc=$(jq -r '.description // ""' "$PLUGIN_JSON" 2>/dev/null || true)
    REPO_URL=$(jq -r '.repo_url // ""' "$PLUGIN_JSON" 2>/dev/null || true)
    if [[ -n "$_desc" ]]; then
      echo "_${_desc}_"
      echo ""
    fi
    if [[ -n "$REPO_URL" ]]; then
      echo "[Source Repository]($REPO_URL)"
      echo ""
    fi
  fi

  TABLE_ROWS=()

  print_table() {
    echo "| Check | Status | Details |"
    echo "|-------|:------:|---------|"
    for row in "${TABLE_ROWS[@]}"; do
      echo "$row"
    done
    echo ""
  }

  # ── Structural checks (hidden if pass) ───────────────────────────────────────

  # Folder name format
  if [[ ! "$PLUGIN_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    TABLE_ROWS+=("| Folder name | ❌ | Must be lowercase-kebab-case - got \`$PLUGIN_NAME\`, e.g. \`my-plugin-name\` |")
    failed=1
  fi

  # plugin.json existence (early exit)
  if [[ ! -f "$PLUGIN_JSON" ]]; then
    TABLE_ROWS+=("| \`plugin.json\` | ❌ | File missing |")
    print_table
    echo "result=fail" >> "$GITHUB_OUTPUT"
    echo "is_new=false" >> "$GITHUB_OUTPUT"
    echo "has_permission=false" >> "$GITHUB_OUTPUT"
    exit 0
  fi

  # JSON syntax (early exit)
  if ! jq empty "$PLUGIN_JSON" 2>/dev/null; then
    TABLE_ROWS+=("| JSON syntax | ❌ | Invalid JSON in plugin.json |")
    print_table
    echo "result=fail" >> "$GITHUB_OUTPUT"
    echo "is_new=false" >> "$GITHUB_OUTPUT"
    echo "has_permission=false" >> "$GITHUB_OUTPUT"
    exit 0
  fi

  # ── Required content ──────────────────────────────────────────────────────────

  # Required fields: name, version, description - shown as a combined row
  MISSING_FIELDS=()
  for key in name version description; do
    if ! jq -e ".\"$key\"" "$PLUGIN_JSON" >/dev/null 2>&1; then
      MISSING_FIELDS+=("\`$key\`")
      failed=1
    fi
  done
  if [[ ${#MISSING_FIELDS[@]} -gt 0 ]]; then
    MISSING_LIST=$(IFS=", "; echo "${MISSING_FIELDS[*]}")
    TABLE_ROWS+=("| Required fields | ❌ | Missing: $MISSING_LIST |")
  else
    TABLE_ROWS+=("| Required fields | ✅ | All required fields present |")
  fi

  # Extract metadata
  AUTHOR=$(jq -r '.author // ""' "$PLUGIN_JSON")
  MAINTAINERS=$(jq -r '[.maintainers[]?] | join(" ")' "$PLUGIN_JSON")
  VERSION=$(jq -r '.version' "$PLUGIN_JSON")

  # Pre-fetch base branch plugin.json once - reused for version bump check and compare link
  _base_pjson=""
  OLD_VERSION=""
  OLD_SOURCE_URL_TMPL=""
  if git show "origin/${BASE_REF}:${PLUGIN_JSON}" > /dev/null 2>&1; then
    _base_pjson=$(git show "origin/${BASE_REF}:${PLUGIN_JSON}")
    OLD_VERSION=$(echo "$_base_pjson" | jq -r '.version // ""')
    OLD_SOURCE_URL_TMPL=$(echo "$_base_pjson" | jq -r '.source_url // ""')
  fi

  # ── External source checks ────────────────────────────────────────────────────
  source_type=$(jq -r '.source_type // "local"' "$PLUGIN_JSON")
  release_link=""
  compare_link=""
  _gh_tag=""
  _old_gh_tag=""
  if [[ "$source_type" != "external" ]]; then
    _src_count=$(find "$PLUGIN_DIR" -type f \
      ! -name 'plugin.json' ! -name 'README.md' ! -name 'logo.png' \
      | wc -l | tr -d ' ')
    if [[ "$_src_count" -eq 0 ]]; then
      TABLE_ROWS+=("| Plugin files | ❌ | No source files found in \`plugins/$PLUGIN_NAME/\`. Add your plugin source (e.g. \`main.py\`) or set \`\"source_type\": \"external\"\` in \`plugin.json\` if your plugin is hosted elsewhere |")
      failed=1
    fi
  fi
  if [[ "$source_type" == "external" ]]; then
    ext_source_url=$(jq -r '.source_url // ""' "$PLUGIN_JSON")
    ext_repo_url=$(jq -r '.repo_url // ""' "$PLUGIN_JSON")

    if [[ -z "$ext_source_url" ]]; then
      TABLE_ROWS+=("| \`source_url\` | ❌ | Required when \`source_type\` is \`external\` |")
      failed=1
    elif [[ ! "$ext_source_url" =~ ^https:// ]]; then
      TABLE_ROWS+=("| \`source_url\` | ❌ | Must be an HTTPS URL |")
      failed=1
    elif [[ "$ext_source_url" != *"{version}"* ]]; then
      TABLE_ROWS+=("| \`source_url\` | ❌ | Must contain a \`{version}\` placeholder (e.g. \`.../v{version}/plugin.zip\`) |")
      failed=1
    else
      # TABLE_ROWS+=("| \`source_url\` | ✅ | \`${ext_source_url}\` |")
      if [[ $(validate_semver "$VERSION") -eq 1 ]]; then
        resolved_url="${ext_source_url//\{version\}/$VERSION}"
        http_code=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 -L "$resolved_url" || echo "000")
        if [[ "$http_code" == "200" ]]; then
          TABLE_ROWS+=("| Release artifact | ✅ | Artifact reachable at resolved URL |")
          if [[ "$resolved_url" =~ ^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/ ]]; then
            _gh_owner="${BASH_REMATCH[1]}"
            _gh_repo="${BASH_REMATCH[2]}"
            _gh_tag="${BASH_REMATCH[3]}"
            release_link="https://github.com/${_gh_owner}/${_gh_repo}/releases/tag/${_gh_tag}"
            if [[ -n "$OLD_VERSION" && -n "$OLD_SOURCE_URL_TMPL" ]]; then
              _old_resolved="${OLD_SOURCE_URL_TMPL//\{version\}/$OLD_VERSION}"
              if [[ "$_old_resolved" =~ ^https://github\.com/[^/]+/[^/]+/releases/download/([^/]+)/ ]]; then
                _old_gh_tag="${BASH_REMATCH[1]}"
                compare_link="https://github.com/${_gh_owner}/${_gh_repo}/compare/${_old_gh_tag}...${_gh_tag}"
              fi
            fi
          fi
        else
          TABLE_ROWS+=("| Release artifact | ❌ | Could not reach \`$resolved_url\` (HTTP \`$http_code\`) — ensure the release exists |")
          failed=1
        fi
      fi
    fi

    if [[ -z "$ext_repo_url" ]]; then
      TABLE_ROWS+=("| \`repo_url\` | ❌ | Required for external plugins — set to the upstream source repository URL |")
      failed=1
    fi
  fi

  # Maintainers
  if [[ -z "$AUTHOR" ]] && [[ -z "$MAINTAINERS" ]]; then
    TABLE_ROWS+=("| Maintainers | ❌ | At least one of \`author\` or \`maintainers\` must include your GitHub username |")
    failed=1
  else
    DISPLAY_PARTS=()
    [[ -n "$AUTHOR" ]] && DISPLAY_PARTS+=("\`$AUTHOR\`")
    for m in $MAINTAINERS; do DISPLAY_PARTS+=("\`$m\`"); done
    DISPLAY=$(printf '%s, ' "${DISPLAY_PARTS[@]}"); DISPLAY="${DISPLAY%, }"
    TABLE_ROWS+=("| Maintainers | ✅ | $DISPLAY |")
  fi

  # License (required)
  LICENSE_ID=$(jq -r '.license // ""' "$PLUGIN_JSON")
  if [[ -z "$LICENSE_ID" ]]; then
    TABLE_ROWS+=("| License | ❌ | \`license\` is required - provide an [OSI-approved SPDX identifier](https://spdx.org/licenses/) (e.g. \`MIT\`, \`Apache-2.0\`) |")
    failed=1
  else
    SPDX_JSON=$(curl -fsSL "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json" 2>/dev/null || echo "")
    if [[ -z "$SPDX_JSON" ]]; then
      TABLE_ROWS+=("| License | ⚠️ | Could not fetch SPDX license list - skipping validation |")
    else
      SPDX_VALID=$(echo "$SPDX_JSON" | jq --arg lid "$LICENSE_ID" '[.licenses[] | select(.isOsiApproved == true) | .licenseId] | any(. == $lid)')
      if [[ "$SPDX_VALID" == "true" ]]; then
        LICENSE_NAME=$(echo "$SPDX_JSON" | jq -r --arg lid "$LICENSE_ID" '.licenses[] | select(.licenseId == $lid) | .name')
        TABLE_ROWS+=("| License | ✅ | \`$LICENSE_ID\` - $LICENSE_NAME |")
      else
        TABLE_ROWS+=("| License | ❌ | \`$LICENSE_ID\` is not an [OSI-approved SPDX identifier](https://spdx.org/licenses/) |")
        failed=1
      fi
    fi
  fi

  # ── Access control ────────────────────────────────────────────────────────────

  # Permission check - use base branch version to prevent self-granting via the PR
  IS_REPO_MAINTAINER=$(check_repo_maintainer "$PR_AUTHOR")
  if [[ "$IS_REPO_MAINTAINER" -eq 1 ]]; then
    TABLE_ROWS+=("| Permission | ✅ | You have permission to modify this plugin |")
    has_permission="true"
  elif git show "origin/${BASE_REF}:${PLUGIN_JSON}" > /dev/null 2>&1; then
    BASE_JSON=$(git show "origin/${BASE_REF}:${PLUGIN_JSON}")
    BASE_AUTHOR=$(echo "$BASE_JSON" | jq -r '.author // ""')
    BASE_MAINTAINERS=$(echo "$BASE_JSON" | jq -r '[.maintainers[]?] | join(" ")')
    if [[ "$PR_AUTHOR" == "$BASE_AUTHOR" ]] || [[ " $BASE_MAINTAINERS " =~ " $PR_AUTHOR " ]]; then
      TABLE_ROWS+=("| Permission | ✅ | You have permission to modify this plugin |")
      has_permission="true"
    else
      TABLE_ROWS+=("| Permission | ❌ | \`$PR_AUTHOR\` is not listed in \`author\` or \`maintainers\` |")
      failed=1
    fi
  else
    # New plugin - PR author must list themselves so future PRs can be authorized
    if [[ "$PR_AUTHOR" == "$AUTHOR" ]] || [[ " $MAINTAINERS " =~ " $PR_AUTHOR " ]]; then
      TABLE_ROWS+=("| Permission | ✅ | New plugin - \`$PR_AUTHOR\` listed in \`author\`/\`maintainers\` |")
      has_permission="true"
    else
      TABLE_ROWS+=("| Permission | ❌ | Add \`\"author\": \"$PR_AUTHOR\"\` to plugin.json |")
      failed=1
    fi
  fi

  # ── Version checks ────────────────────────────────────────────────────────────

  # Version format
  if [[ $(validate_semver "$VERSION") -eq 1 ]]; then
    TABLE_ROWS+=("| Version | ✅ | \`$VERSION\` |")
  else
    TABLE_ROWS+=("| Version | ❌ | \`$VERSION\` is not valid semver - expected \`X.Y.Z\` |")
    failed=1
  fi

  # Version bump
  # These fields may be updated without a version bump - they are metadata only
  # and do not affect the packaged ZIP artifact.
  METADATA_ONLY_FIELDS=("description" "repo_url" "discord_thread"
    "min_dispatcharr_version" "max_dispatcharr_version" "deprecated" "unlisted" "maintainers")

  if [[ -n "$_base_pjson" ]]; then
    if version_greater_than "$VERSION" "$OLD_VERSION"; then
      TABLE_ROWS+=("| Version bump | ✅ | \`$OLD_VERSION\` → \`$VERSION\` |")
    else
      # Version unchanged - check if every changed field is in the metadata-only allowlist
      OLD_JSON="$_base_pjson"
      NEW_JSON=$(cat "$PLUGIN_JSON")

      # Produce a newline-separated list of field names that differ (raw strings, no quotes)
      changed_fields=$(jq -rn \
        --argjson old "$OLD_JSON" \
        --argjson new "$NEW_JSON" \
        '[$new | keys[]] | map(select($old[.] != $new[.])) | .[]' 2>/dev/null || true)

      metadata_only_change=true
      while IFS= read -r field; do
        [[ -z "$field" ]] && continue
        allowed=false
        for mf in "${METADATA_ONLY_FIELDS[@]}"; do
          [[ "$field" == "$mf" ]] && allowed=true && break
        done
        $allowed || { metadata_only_change=false; break; }
      done <<< "$changed_fields"

      if $metadata_only_change && [[ -n "$changed_fields" ]]; then
        TABLE_ROWS+=("| Version bump | ✅ | \`$OLD_VERSION\` (unchanged - metadata-only update) |")
      else
        # Any non-metadata plugin.json change or other file change requires a version bump.
        # If plugin.json is identical, check whether other files in the directory changed
        # so we can give a more accurate error message.
        _other_changed=""
        if [[ -z "$changed_fields" ]]; then
          _other_changed=$(git diff --name-only "origin/${BASE_REF}...HEAD" -- "$PLUGIN_DIR" \
            | grep -v "^${PLUGIN_JSON}$" | head -1 || true)
        fi
        if [[ -z "$changed_fields" && -z "$_other_changed" ]]; then
          TABLE_ROWS+=("| Version bump | ❌ | No changes detected - nothing to publish |")
        else
          TABLE_ROWS+=("| Version bump | ❌ | \`$VERSION\` must be greater than current \`$OLD_VERSION\` |")
        fi
        failed=1
      fi
    fi
  else
    TABLE_ROWS+=("| Version bump | ✅ | New plugin |")
    is_new="true"
  fi

  # Dispatcharr version constraints (optional, hidden if pass)
  MIN_DA_VERSION=$(jq -r '.min_dispatcharr_version // ""' "$PLUGIN_JSON")
  MAX_DA_VERSION=$(jq -r '.max_dispatcharr_version // ""' "$PLUGIN_JSON")

  if [[ -n "$MIN_DA_VERSION" ]] && [[ $(validate_dispatcharr_version "$MIN_DA_VERSION") -eq 0 ]]; then
    TABLE_ROWS+=("| \`min_dispatcharr_version\` | ❌ | \`$MIN_DA_VERSION\` is not valid semver - expected \`X.Y.Z\` or \`vX.Y.Z\` |")
    failed=1
  fi

  if [[ -n "$MAX_DA_VERSION" ]] && [[ $(validate_dispatcharr_version "$MAX_DA_VERSION") -eq 0 ]]; then
    TABLE_ROWS+=("| \`max_dispatcharr_version\` | ❌ | \`$MAX_DA_VERSION\` is not valid semver - expected \`X.Y.Z\` or \`vX.Y.Z\` |")
    failed=1
  fi

  # min/max range sanity (hidden if pass)
  if [[ -n "$MIN_DA_VERSION" && -n "$MAX_DA_VERSION" ]]; then
    if [[ $(validate_dispatcharr_version "$MAX_DA_VERSION") -eq 1 && $(validate_dispatcharr_version "$MIN_DA_VERSION") -eq 1 ]]; then
      _max="${MAX_DA_VERSION#v}"
      _min="${MIN_DA_VERSION#v}"
      if ! version_greater_than "$_max" "$_min" && [[ "$_max" != "$_min" ]]; then
        TABLE_ROWS+=("| Version range | ❌ | \`max_dispatcharr_version\` (\`$MAX_DA_VERSION\`) must be ≥ \`min_dispatcharr_version\` (\`$MIN_DA_VERSION\`) |")
        failed=1
      fi
    fi
  fi

  # ── Optional link fields (hidden if pass) ────────────────────────────────────

  DISCORD_THREAD=$(jq -r '.discord_thread // ""' "$PLUGIN_JSON")

  if [[ -n "$REPO_URL" ]] && [[ ! "$REPO_URL" =~ ^https?:// ]]; then
    TABLE_ROWS+=("| \`repo_url\` | ❌ | Must start with \`http://\` or \`https://\` |")
    failed=1
  fi

  if [[ -n "$DISCORD_THREAD" ]] && [[ ! "$DISCORD_THREAD" =~ ^https?:// ]]; then
    TABLE_ROWS+=("| \`discord_thread\` | ❌ | Must start with \`http://\` or \`https://\` |")
    failed=1
  fi

  print_table

  if [[ -n "$release_link" ]]; then
    _link_line="[View release ${_gh_tag} on GitHub](${release_link})"
    [[ -n "$compare_link" ]] && _link_line+=" · [Compare ${_old_gh_tag}...${_gh_tag}](${compare_link})"
    echo "$_link_line"
    echo ""
  fi

  # Metadata row (tab-delimited, consumed by aggregate-report.sh)
  echo "<!--META_ROW:$(jq -r '[
    .name // "",
    .version // "",
    .description // "",
    .author // "",
    ([ .maintainers[]? ] | join(", ")),
    (.repo_url // ""),
    (.discord_thread // "")
  ] | @tsv' "$PLUGIN_JSON")-->"

} > "$OUTPUT_FILE"


# Write job outputs
if [[ $failed -eq 0 ]]; then
  echo "result=pass" >> "$GITHUB_OUTPUT"
else
  echo "result=fail" >> "$GITHUB_OUTPUT"
fi
echo "is_new=$is_new" >> "$GITHUB_OUTPUT"
echo "has_permission=$has_permission" >> "$GITHUB_OUTPUT"

exit $failed
