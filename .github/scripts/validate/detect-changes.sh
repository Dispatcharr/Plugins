#!/bin/bash
set -e

# detect-changes.sh
# Detects which plugins were modified in a PR, checks .github/ protection,
# and determines whether the PR should be auto-closed for lack of permission.
#
# Usage: detect-changes.sh <pr_author> <base_ref>
#
# Outputs (written to $GITHUB_OUTPUT):
#   matrix        - JSON array of plugin names for matrix strategy
#   plugin_count  - Number of modified plugins
#   close_pr      - "true" if the PR should be auto-closed (no permission, no new plugins)
#
# Exit codes:
#   0  - OK (matrix emitted, proceed to validation)
#   1  - Hard block (e.g. .github/ modification by unauthorized user, no plugin changes)

PR_AUTHOR=$1
BASE_REF=$2

if [[ -z "$PR_AUTHOR" || -z "$BASE_REF" ]]; then
  echo "Usage: $0 <pr_author> <base_ref>"
  exit 1
fi

REPO_OWNER=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f1)
REPO_NAME=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f2)

has_write_access() {
  local author=$1
  local perm
  perm=$(gh api repos/$REPO_OWNER/$REPO_NAME/collaborators/$author/permission --jq .permission 2>/dev/null || echo "none")
  if [[ "$perm" == "admin" || "$perm" == "maintain" || "$perm" == "write" ]]; then
    echo "1"
  else
    echo "0"
  fi
}

MERGE_BASE=$(git merge-base "origin/${BASE_REF}" HEAD)

# --- Protection check: only plugins/ may be modified by non-maintainers ---
OUTSIDE_CHANGES=$(git diff --name-only "$MERGE_BASE" HEAD | grep -v '^plugins/' || true)
HAS_OUTSIDE_VIOLATION=0
if [[ -n "$OUTSIDE_CHANGES" ]] && [[ "$(has_write_access "$PR_AUTHOR")" -ne 1 ]]; then
  HAS_OUTSIDE_VIOLATION=1
fi

# --- Detect modified plugins ---
PLUGIN_LIST=$(git diff --name-only "$MERGE_BASE" HEAD \
  | grep '^plugins/' | cut -d '/' -f2 | sort -u)

if [[ -z "$PLUGIN_LIST" ]]; then
  if [[ $HAS_OUTSIDE_VIOLATION -eq 1 ]]; then
    # Unauthorized outside-plugins changes with no plugin changes
    echo "matrix=[]"              >> "$GITHUB_OUTPUT"
    echo "plugin_count=0"         >> "$GITHUB_OUTPUT"
    echo "close_pr=false"         >> "$GITHUB_OUTPUT"
    echo "close_reason="          >> "$GITHUB_OUTPUT"
    echo "skip_validation=false"  >> "$GITHUB_OUTPUT"
    echo "outside_violation=true" >> "$GITHUB_OUTPUT"
    echo "has_new_plugin=false"    >> "$GITHUB_OUTPUT"
    echo "has_updated_plugin=false" >> "$GITHUB_OUTPUT"
    {
      echo "outside_files<<OUTSIDE_EOF"
      echo "$OUTSIDE_CHANGES"
      echo "OUTSIDE_EOF"
    } >> "$GITHUB_OUTPUT"
    exit 0
  fi
  if [[ "$(has_write_access "$PR_AUTHOR")" -eq 1 ]]; then
    # Repo maintainer with no plugin changes - skip plugin validation entirely and pass
    PUB_KEY_CHANGED=false
    if echo "$OUTSIDE_CHANGES" | grep -q "^\.github/scripts/keys/dispatcharr-plugins\.pub$"; then
      PUB_KEY_CHANGED=true
    fi
    echo "matrix=[]"               >> "$GITHUB_OUTPUT"
    echo "plugin_count=0"          >> "$GITHUB_OUTPUT"
    echo "close_pr=false"          >> "$GITHUB_OUTPUT"
    echo "close_reason="           >> "$GITHUB_OUTPUT"
    echo "skip_validation=true"    >> "$GITHUB_OUTPUT"
    echo "outside_violation=false" >> "$GITHUB_OUTPUT"
    echo "pub_key_changed=$PUB_KEY_CHANGED" >> "$GITHUB_OUTPUT"
    echo "has_new_plugin=false"              >> "$GITHUB_OUTPUT"
    echo "has_updated_plugin=false"          >> "$GITHUB_OUTPUT"
    if [[ -n "$OUTSIDE_CHANGES" ]]; then
      {
        echo "outside_files<<OUTSIDE_EOF"
        echo "$OUTSIDE_CHANGES"
        echo "OUTSIDE_EOF"
      } >> "$GITHUB_OUTPUT"
    fi
    echo "No plugin changes detected - skipping plugin validation (author has write access)."
    exit 0
  fi
  echo "::error::No plugin changes detected in this PR."
  exit 1
fi

# --- Allowlist: only accept safe lowercase-kebab-case names before they enter the matrix ---
SAFE_LIST=""
while IFS= read -r plugin; do
  [[ -z "$plugin" ]] && continue
  if [[ "$plugin" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    SAFE_LIST+="${plugin}"$'\n'
  else
    echo "::warning::Skipping plugin with unsafe folder name: '${plugin}'"
  fi
done <<< "$PLUGIN_LIST"
PLUGIN_LIST=$(printf '%s' "$SAFE_LIST" | grep . || true)

if [[ -z "$PLUGIN_LIST" ]]; then
  echo "::error::No valid plugin changes detected in this PR."
  echo "close_pr=true"              >> "$GITHUB_OUTPUT"
  echo "close_reason=no-valid-plugins" >> "$GITHUB_OUTPUT"
  echo "plugin_count=0"             >> "$GITHUB_OUTPUT"
  echo "matrix=[]"                  >> "$GITHUB_OUTPUT"
  echo "has_new_plugin=false"       >> "$GITHUB_OUTPUT"
  echo "has_updated_plugin=false"   >> "$GITHUB_OUTPUT"
  exit 0
fi

PLUGIN_COUNT=$(echo "$PLUGIN_LIST" | wc -l | tr -d ' ')

# --- Check if any modified plugin is new / updated ---
HAS_NEW_PLUGIN=0
HAS_UPDATED_PLUGIN=0
while IFS= read -r plugin; do
  [[ -z "$plugin" ]] && continue
  if ! git show "origin/${BASE_REF}:plugins/${plugin}/plugin.json" > /dev/null 2>&1; then
    HAS_NEW_PLUGIN=1
  else
    HAS_UPDATED_PLUGIN=1
  fi
done <<< "$PLUGIN_LIST"

# --- Check if PR author has permission for at least one modified plugin ---
HAS_ANY_PERMISSION=0
IS_REPO_MAINTAINER=$(has_write_access "$PR_AUTHOR")
if [[ "$IS_REPO_MAINTAINER" -eq 1 ]]; then
  HAS_ANY_PERMISSION=1
else
  while IFS= read -r plugin; do
    [[ -z "$plugin" ]] && continue
    # Read from base branch to prevent self-granting permission via the PR itself
    BASE_JSON=$(git show "origin/${BASE_REF}:plugins/${plugin}/plugin.json" 2>/dev/null || echo "")
    if [[ -n "$BASE_JSON" ]]; then
      AUTHOR=$(echo "$BASE_JSON" | jq -r '.author // ""')
      MAINTAINERS=$(echo "$BASE_JSON" | jq -r '[.maintainers[]?] | join(" ")')
      if [[ "$PR_AUTHOR" == "$AUTHOR" ]] || [[ " $MAINTAINERS " =~ " $PR_AUTHOR " ]]; then
        HAS_ANY_PERMISSION=1
        break
      fi
    fi
    # New plugins (no base version) are handled by HAS_NEW_PLUGIN above
  done <<< "$PLUGIN_LIST"
fi

# Determine if this PR should be auto-closed:
# Only close if the author has no permission AND there are no new plugins
CLOSE_PR="false"
if [[ $HAS_ANY_PERMISSION -eq 0 ]] && [[ $HAS_NEW_PLUGIN -eq 0 ]]; then
  CLOSE_PR="true"
fi

# Build JSON matrix array
MATRIX_JSON=$(echo "$PLUGIN_LIST" | jq -Rnc '[inputs]')

echo "matrix=$MATRIX_JSON" >> "$GITHUB_OUTPUT"
echo "plugin_count=$PLUGIN_COUNT" >> "$GITHUB_OUTPUT"
echo "close_pr=$CLOSE_PR" >> "$GITHUB_OUTPUT"
echo "skip_validation=false" >> "$GITHUB_OUTPUT"
if [[ $HAS_OUTSIDE_VIOLATION -eq 1 ]]; then
  echo "outside_violation=true" >> "$GITHUB_OUTPUT"
else
  echo "outside_violation=false" >> "$GITHUB_OUTPUT"
fi
if [[ "$CLOSE_PR" == "true" ]]; then
  echo "close_reason=unauthorized" >> "$GITHUB_OUTPUT"
else
  echo "close_reason=" >> "$GITHUB_OUTPUT"
fi
if [[ -n "$OUTSIDE_CHANGES" ]]; then
  {
    echo "outside_files<<OUTSIDE_EOF"
    echo "$OUTSIDE_CHANGES"
    echo "OUTSIDE_EOF"
  } >> "$GITHUB_OUTPUT"
fi

# Warn when an authorized contributor changes the signing public key
PUB_KEY_CHANGED=false
if [[ "$(has_write_access "$PR_AUTHOR")" -eq 1 ]]; then
  if echo "$OUTSIDE_CHANGES" | grep -q "^\.github/scripts/keys/dispatcharr-plugins\.pub$"; then
    PUB_KEY_CHANGED=true
  fi
fi
echo "pub_key_changed=$PUB_KEY_CHANGED" >> "$GITHUB_OUTPUT"

echo "has_new_plugin=$( [[ $HAS_NEW_PLUGIN -eq 1 ]] && echo true || echo false )" >> "$GITHUB_OUTPUT"
echo "has_updated_plugin=$( [[ $HAS_UPDATED_PLUGIN -eq 1 ]] && echo true || echo false )" >> "$GITHUB_OUTPUT"

echo "Detected $PLUGIN_COUNT plugin(s): $PLUGIN_LIST"
echo "close_pr=$CLOSE_PR"
