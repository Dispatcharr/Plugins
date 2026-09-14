#!/bin/bash
set -e

# yank-version.sh
# Removes a specific version of a plugin from the releases branch and regenerates
# manifests and READMEs. If the yanked version is the current latest, the previous
# version is promoted to latest. If it is the only version, the plugin is fully
# removed. A rollback PR is opened against the source branch when the latest (or
# only) version is yanked.
#
# Environment variables required:
#   GITHUB_REPOSITORY - Full repository name (owner/repo)
#   GITHUB_TOKEN      - GitHub token with write access and PR creation permission
#   YANK_PLUGIN       - Plugin slug (e.g. dispatcharr-exporter)
#   YANK_VERSION      - Version to remove (e.g. 3.0.1)
#   SOURCE_BRANCH     - Source branch to fetch plugin metadata from (e.g. main)

: "${GITHUB_REPOSITORY:?}" "${GITHUB_TOKEN:?}" "${YANK_PLUGIN:?}" "${YANK_VERSION:?}" "${SOURCE_BRANCH:?}" "${YANK_ISSUE:?}"

RELEASES_BRANCH="releases"
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

export SOURCE_BRANCH RELEASES_BRANCH GITHUB_REPOSITORY

echo "Yanking $YANK_PLUGIN v$YANK_VERSION from $RELEASES_BRANCH (issue #$YANK_ISSUE)"

# --- Validate issue ---
ISSUE_STATE=$(gh api "repos/$GITHUB_REPOSITORY/issues/$YANK_ISSUE" --jq '.state' 2>/dev/null || true)
if [[ -z "$ISSUE_STATE" ]]; then
  echo "::error::Issue #$YANK_ISSUE not found in $GITHUB_REPOSITORY."
  exit 1
fi
if [[ "$ISSUE_STATE" != "open" ]]; then
  echo "::error::Issue #$YANK_ISSUE is already $ISSUE_STATE. Only open issues can authorize a yank."
  exit 1
fi
echo "  Issue #$YANK_ISSUE is open - proceeding."

WORK_DIR=$(mktemp -d)
BUILD_META_DIR=$(mktemp -d)
export BUILD_META_DIR
trap 'rm -rf "$WORK_DIR" "$BUILD_META_DIR"' EXIT

echo "Cloning repository..."
git clone --no-checkout "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$WORK_DIR/repo"
cd "$WORK_DIR/repo"

# Configure git identity
if [[ -n "${APP_SLUG:-}" ]]; then
  BOT_USER_ID=$(gh api "/users/${APP_SLUG}%5Bbot%5D" --jq '.id' 2>/dev/null || echo "")
  git config user.name "${APP_SLUG}[bot]"
  if [[ -n "$BOT_USER_ID" ]]; then
    git config user.email "${BOT_USER_ID}+${APP_SLUG}[bot]@users.noreply.github.com"
  else
    git config user.email "${APP_SLUG}[bot]@users.noreply.github.com"
  fi
else
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
fi

# Checkout releases branch
if git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
  git checkout $RELEASES_BRANCH
  git pull origin $RELEASES_BRANCH || true
else
  echo "::error::Releases branch does not exist."
  exit 1
fi

ZIP_DIR="metadata/$YANK_PLUGIN"
RELEASE_TAG="${YANK_PLUGIN}-${YANK_VERSION}"
PLUGIN_MANIFEST="$ZIP_DIR/manifest.json"

# --- Validate ---
if ! gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
  echo "::error::GitHub Release $RELEASE_TAG not found. Nothing to yank."
  exit 1
fi

# Count remaining versioned releases (excluding the one being yanked and -latest)
REMAINING=$(gh release list --repo "$GITHUB_REPOSITORY" --json tagName --limit 500 \
  | jq -r '.[].tagName' \
  | grep "^${YANK_PLUGIN}-" \
  | grep -v "^${YANK_PLUGIN}-latest$" \
  | grep -v "^${RELEASE_TAG}$" || true)
REMAINING_COUNT=$(echo "$REMAINING" | grep -c . || true)

# Determine if we are yanking the current latest
CURRENT_LATEST=""
if [[ -f "$PLUGIN_MANIFEST" ]]; then
  CURRENT_LATEST=$(jq -r '.manifest.latest.version // ""' "$PLUGIN_MANIFEST" 2>/dev/null || true)
fi
IS_LATEST=false
[[ "$YANK_VERSION" == "$CURRENT_LATEST" ]] && IS_LATEST=true

IS_LAST_VERSION=false
[[ "$REMAINING_COUNT" -eq 0 ]] && IS_LAST_VERSION=true

echo "  Current latest   : ${CURRENT_LATEST:-unknown}"
echo "  Is latest        : $IS_LATEST"
echo "  Remaining releases: $REMAINING_COUNT"
echo "  Is last version  : $IS_LAST_VERSION"

# --- Fetch source branch + plugins dir (needed by manifest + readme scripts) ---
git fetch origin "$SOURCE_BRANCH"
git checkout "origin/$SOURCE_BRANCH" -- plugins

# Determine source_type before deleting anything
SOURCE_TYPE=$(jq -r '.source_type // "local"' "plugins/$YANK_PLUGIN/plugin.json" 2>/dev/null || echo "local")

# --- Perform the yank ---
if $IS_LAST_VERSION; then
  echo "Last version - deleting all GitHub Releases for $YANK_PLUGIN."
  gh release delete "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag
  rm -rf "$ZIP_DIR"
else
  echo "Deleting GitHub Release $RELEASE_TAG"
  gh release delete "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag

  if $IS_LATEST; then
    NEW_LATEST_VERSION=$(echo "$REMAINING" \
      | sed "s/^${YANK_PLUGIN}-//" \
      | sort -V -r \
      | head -1)
    if [[ -z "$NEW_LATEST_VERSION" ]]; then
      echo "::error::Could not find a replacement version to promote to latest."
      exit 1
    fi
    echo "Promoting $NEW_LATEST_VERSION to latest (manifest will be updated by generate-manifest.sh)"
  fi
fi

# --- Regenerate manifests and READMEs ---
rm -f manifest.json README.md

echo ""
echo "=== Regenerating manifests ==="
bash "$SCRIPT_DIR/generate-manifest.sh"

echo ""
echo "=== Regenerating per-plugin READMEs ==="
bash "$SCRIPT_DIR/plugin-readmes.sh"

echo ""
echo "=== Regenerating releases README ==="
bash "$SCRIPT_DIR/releases-readme.sh"

# --- Commit and push ---
echo ""
echo "=== Committing ==="
rm -rf plugins
git rm -rf --cached plugins 2>/dev/null || true

git add metadata manifest.json README.md

if git diff --cached --quiet; then
  echo "No changes to commit - was this version already absent?"
else
  git commit -m "Yank ${YANK_PLUGIN} v${YANK_VERSION}

Refs #${YANK_ISSUE}"
  RELEASES_COMMIT=$(git rev-parse --short HEAD)
  git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" $RELEASES_BRANCH
  echo "Successfully yanked ${YANK_PLUGIN} v${YANK_VERSION} from ${RELEASES_BRANCH}"
fi

ROLLBACK_PR_URL=""

# --- Open rollback PR if we yanked the latest (or only) version ---
if $IS_LATEST; then
  echo ""
  echo "=== Opening rollback PR ==="

  REPO_OWNER=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f1)
  REPO_NAME=$(echo "$GITHUB_REPOSITORY" | cut -d'/' -f2)
  ROLLBACK_BRANCH="yank/${YANK_PLUGIN}-${YANK_VERSION}"

  # Start rollback branch from source branch tip
  git fetch origin "$SOURCE_BRANCH"
  git checkout -b "$ROLLBACK_BRANCH" "origin/$SOURCE_BRANCH"

  if $IS_LAST_VERSION; then
    # Remove the plugin from source entirely
    git rm -rf "plugins/$YANK_PLUGIN"
    PR_TITLE="[${YANK_PLUGIN}]: Remove plugin (all versions yanked)"
    PR_BODY="## Plugin Removed

All published versions of \`${YANK_PLUGIN}\` have been yanked from the releases branch.

This PR removes the plugin from the source branch to prevent it from being republished on the next run.

**Yanked version:** \`${YANK_VERSION}\`
**Authorized by:** #${YANK_ISSUE}

Closes #${YANK_ISSUE}"
  else
    # Roll back plugin source to the new-latest version
    if [[ "$SOURCE_TYPE" == "local" ]]; then
      # Find the most recent commit where plugin.json had the target version
      RESTORE_COMMIT=$(git log --all --format="%H" -- "plugins/$YANK_PLUGIN/plugin.json" | while IFS= read -r sha; do
        v=$(git show "${sha}:plugins/${YANK_PLUGIN}/plugin.json" 2>/dev/null | jq -r '.version // ""' 2>/dev/null || true)
        if [[ "$v" == "$NEW_LATEST_VERSION" ]]; then
          echo "$sha"
          break
        fi
      done)

      if [[ -n "$RESTORE_COMMIT" ]]; then
        echo "Restoring plugins/$YANK_PLUGIN/ from commit $RESTORE_COMMIT"
        git checkout "$RESTORE_COMMIT" -- "plugins/$YANK_PLUGIN/"
        SOURCE_NOTE="Plugin source files restored from commit \`${RESTORE_COMMIT:0:7}\` (the last commit where \`${YANK_PLUGIN}\` was at \`${NEW_LATEST_VERSION}\`)."
      else
        echo "::warning::Could not find a commit for $YANK_PLUGIN v$NEW_LATEST_VERSION - falling back to version field update only."
        jq --arg v "$NEW_LATEST_VERSION" '.version = $v' "plugins/$YANK_PLUGIN/plugin.json" > /tmp/plugin.json.tmp
        mv /tmp/plugin.json.tmp "plugins/$YANK_PLUGIN/plugin.json"
        SOURCE_NOTE="⚠️ **Could not restore source files** - no commit found for \`${NEW_LATEST_VERSION}\` (history may have been squashed). Only the \`version\` field was updated. Please review the source files manually before merging."
      fi
    else
      # External plugin: only the version field needs to change
      jq --arg v "$NEW_LATEST_VERSION" '.version = $v' "plugins/$YANK_PLUGIN/plugin.json" > /tmp/plugin.json.tmp
      mv /tmp/plugin.json.tmp "plugins/$YANK_PLUGIN/plugin.json"
      SOURCE_NOTE="Version field in \`plugin.json\` updated to \`${NEW_LATEST_VERSION}\`. The ZIP will be re-fetched from the external source URL on the next publish run."
    fi

    git add "plugins/$YANK_PLUGIN/"
    PR_TITLE="[${YANK_PLUGIN}]: Roll back to v${NEW_LATEST_VERSION} (yank of v${YANK_VERSION})"
    PR_BODY="## Version Rollback

\`${YANK_PLUGIN}\` \`${YANK_VERSION}\` has been yanked from the releases branch. This PR rolls the source back to \`${NEW_LATEST_VERSION}\` so the yanked version is not republished on the next run.

**Yanked version:** \`${YANK_VERSION}\`
**New latest:** \`${NEW_LATEST_VERSION}\`
**Authorized by:** #${YANK_ISSUE}

${SOURCE_NOTE}

Closes #${YANK_ISSUE}"
  fi

  git commit -m "$PR_TITLE"
  git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$ROLLBACK_BRANCH"

  # Ensure the Rollback label exists
  gh label create "Rollback" \
    --color "E11D48" \
    --description "Version rollback opened by the yank workflow" \
    --repo "$GITHUB_REPOSITORY" 2>/dev/null || true

  ROLLBACK_PR_URL=$(gh pr create \
    --repo "$GITHUB_REPOSITORY" \
    --base "$SOURCE_BRANCH" \
    --head "$ROLLBACK_BRANCH" \
    --title "$PR_TITLE" \
    --label "Rollback" \
    --body "$PR_BODY")

  echo "Rollback PR opened: $ROLLBACK_BRANCH -> $SOURCE_BRANCH ($ROLLBACK_PR_URL)"
fi

# --- Comment on the issue; close directly only if no rollback PR is pending ---
if $IS_LATEST; then
  # Issue will be auto-closed when the rollback PR is merged (via Closes #N in PR body).
  # Leave a comment pointing to the PR so the requester can track progress.
  gh issue comment "$YANK_ISSUE" \
    --repo "$GITHUB_REPOSITORY" \
    --body "\`${YANK_PLUGIN}\` v\`${YANK_VERSION}\` has been removed from the releases branch (commit \`${RELEASES_COMMIT:-unknown}\`).

A rollback PR has been opened to update the source branch: ${ROLLBACK_PR_URL:-"(see workflow run for link)"}

This issue will close automatically when that PR is merged."
else
  # No rollback PR - close the issue directly.
  gh issue comment "$YANK_ISSUE" \
    --repo "$GITHUB_REPOSITORY" \
    --body "\`${YANK_PLUGIN}\` v\`${YANK_VERSION}\` has been removed from the releases branch (commit \`${RELEASES_COMMIT:-unknown}\`).

This was not the latest version so no source branch changes are needed."

  gh issue close "$YANK_ISSUE" \
    --repo "$GITHUB_REPOSITORY" \
    --reason "completed"
fi
