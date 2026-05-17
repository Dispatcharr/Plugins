#!/bin/bash
set -e

# publish-plugins.sh
# Orchestrates plugin publishing: sets up the releases branch working directory,
# runs each publish phase via subscripts, then commits and pushes.
#
# Usage: publish-plugins.sh <source_branch>
#
# Environment variables required:
#   GITHUB_REPOSITORY - Full repository name (owner/repo)
#   GITHUB_TOKEN      - GitHub token with write access

SOURCE_BRANCH=$1

if [[ -z "$SOURCE_BRANCH" ]]; then
  echo "Usage: $0 <source_branch>"
  exit 1
fi

RELEASES_BRANCH="releases"
MAX_VERSIONED_ZIPS=10
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

export SOURCE_BRANCH RELEASES_BRANCH MAX_VERSIONED_ZIPS

echo "Publishing plugins from $SOURCE_BRANCH to $RELEASES_BRANCH"

# Create temporary working directories
WORK_DIR=$(mktemp -d)
BUILD_META_DIR=$(mktemp -d)
export BUILD_META_DIR
trap 'rm -rf "$WORK_DIR" "$BUILD_META_DIR"' EXIT

echo "Cloning repository..."
git clone --no-checkout "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$WORK_DIR/repo"
cd "$WORK_DIR/repo"

# Configure git - use GitHub App bot identity when available, otherwise fall back
# to the generic github-actions[bot] identity.
# NOTE: the email uses the bot *user* ID (not the App ID) - GitHub resolves commit
# authorship by matching this ID+slug[bot]@users.noreply.github.com to the bot account.
if [[ -n "${APP_SLUG:-}" ]]; then
  BOT_USER_ID=$(gh api "/users/${APP_SLUG}%5Bbot%5D" --jq '.id' 2>/dev/null || echo "")
  git config user.name "${APP_SLUG}[bot]"
  if [[ -n "$BOT_USER_ID" ]]; then
    git config user.email "${BOT_USER_ID}+${APP_SLUG}[bot]@users.noreply.github.com"
  else
    # Fallback if the API call fails - avatar may not resolve but commits still work
    git config user.email "${APP_SLUG}[bot]@users.noreply.github.com"
  fi
else
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
fi

# Checkout or create releases branch
echo "Setting up $RELEASES_BRANCH branch..."
if [[ "${FORCE_REBUILD:-false}" == "true" && -n "${FORCE_REBUILD_PLUGIN:-}" ]]; then
  # Targeted rebuild: keep existing releases branch, clear only the named plugin's zips dir.
  # build-zips.sh will rebuild it since the zip is gone; all other plugins are untouched.
  if git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
    git checkout $RELEASES_BRANCH
    git pull origin $RELEASES_BRANCH || true
  else
    git checkout --orphan $RELEASES_BRANCH
    git rm -rf . 2>/dev/null || true
    git commit --allow-empty -m "Initialize $RELEASES_BRANCH branch"
  fi
  echo "Targeted force rebuild: clearing zips/$FORCE_REBUILD_PLUGIN/"
  rm -rf "zips/$FORCE_REBUILD_PLUGIN"
elif [[ "${FORCE_REBUILD:-false}" == "true" ]]; then
  echo "Force rebuild requested - resetting $RELEASES_BRANCH to a new orphan commit."
  git checkout --orphan $RELEASES_BRANCH
  git rm -rf . 2>/dev/null || true
  git commit --allow-empty -m "Initialize $RELEASES_BRANCH branch (force rebuild)"
  git push --force "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" $RELEASES_BRANCH
elif git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
  git checkout $RELEASES_BRANCH
  git pull origin $RELEASES_BRANCH || true
else
  git checkout --orphan $RELEASES_BRANCH
  git rm -rf . 2>/dev/null || true
  git commit --allow-empty -m "Initialize $RELEASES_BRANCH branch"
fi

# Clean old top-level artifacts (regenerated each run)
rm -f manifest.json README.md

# Fetch source branch and copy plugins
echo "Fetching plugins from $SOURCE_BRANCH..."
git fetch origin $SOURCE_BRANCH
git checkout origin/$SOURCE_BRANCH -- plugins

mkdir -p zips

# --- Phases ---
echo ""
echo "=== Building ZIPs ==="
bash "$SCRIPT_DIR/build-zips.sh"

echo ""
echo "=== Cleaning up old releases ==="
bash "$SCRIPT_DIR/cleanup.sh"

echo ""
echo "=== Generating manifests ==="
bash "$SCRIPT_DIR/generate-manifest.sh"

echo ""
echo "=== Generating per-plugin READMEs ==="
bash "$SCRIPT_DIR/plugin-readmes.sh"

echo ""
echo "=== Generating releases README ==="
bash "$SCRIPT_DIR/releases-readme.sh"

# --- Commit and push ---
echo ""
echo "=== Committing ==="
rm -rf plugins
git rm -rf --cached plugins 2>/dev/null || true

git add zips manifest.json README.md

if git diff --cached --quiet; then
  echo "No changes to commit."
else
  # Check whether the staged diff is purely timestamp noise:
  #   README.md  - "*Last updated: ..." footer
  #   manifest.json - "generated_at" field
  # Any other changed file (e.g. a ZIP) counts as a real change.
  only_timestamps=true
  while IFS= read -r changed_file; do
    case "$changed_file" in
      README.md)
        new_content=$(git show :README.md | grep -v '^\*Last updated:')
        old_content=$(git show HEAD:README.md 2>/dev/null | grep -v '^\*Last updated:' || true)
        [[ "$new_content" == "$old_content" ]] || only_timestamps=false
        ;;
      manifest.json)
        new_content=$(git show :manifest.json | grep -v '"generated_at"')
        old_content=$(git show HEAD:manifest.json 2>/dev/null | grep -v '"generated_at"' || true)
        [[ "$new_content" == "$old_content" ]] || only_timestamps=false
        ;;
      *)
        only_timestamps=false
        ;;
    esac
    $only_timestamps || break
  done < <(git diff --cached --name-only)

  if $only_timestamps; then
    echo "No meaningful changes (only timestamps updated) - skipping commit."
  else
    source_commit=$(git rev-parse --short origin/$SOURCE_BRANCH)
    plugin_list=""
    if [[ -s changed_plugins.txt ]]; then
      plugin_list="$(printf '\n\n')$(sed 's/^/- /' changed_plugins.txt)"
    fi

    git commit -m "Publish plugin updates from $SOURCE_BRANCH

Source commit: $source_commit${plugin_list}

[skip ci]"

    git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" $RELEASES_BRANCH
    echo "Successfully published to ${RELEASES_BRANCH}"
  fi  # end only_timestamps check
fi
