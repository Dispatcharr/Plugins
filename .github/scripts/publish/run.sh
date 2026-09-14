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
RELEASES_BRANCH_VERSION=3
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
  # Targeted rebuild: delete all GitHub Releases for the named plugin so build-zips.sh
  # treats it as new, then clear its per-plugin manifest so generate-manifest.sh
  # rebuilds it from scratch. All other plugins are untouched.
  if git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
    git checkout $RELEASES_BRANCH
    git pull origin $RELEASES_BRANCH || true
  else
    git checkout --orphan $RELEASES_BRANCH
    git rm -rf . 2>/dev/null || true
    git commit --allow-empty -m "Initialize $RELEASES_BRANCH branch"
  fi
  echo "Targeted force rebuild: deleting GitHub Releases for $FORCE_REBUILD_PLUGIN"
  gh release list --repo "$GITHUB_REPOSITORY" --json tagName --limit 500 \
    | jq -r '.[].tagName' \
    | grep "^${FORCE_REBUILD_PLUGIN}-" \
    | xargs -I{} gh release delete {} --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag 2>/dev/null || true
  rm -f "metadata/$FORCE_REBUILD_PLUGIN/manifest.json"
elif [[ "${FORCE_REBUILD:-false}" == "true" ]]; then
  echo "Force rebuild requested - deleting all plugin GitHub Releases and resetting $RELEASES_BRANCH."
  git fetch origin $SOURCE_BRANCH 2>/dev/null || true
  git checkout "origin/$SOURCE_BRANCH" -- plugins 2>/dev/null || true
  if [[ -d plugins ]]; then
    for plugin_dir in plugins/*/; do
      plugin_name=$(basename "$plugin_dir")
      gh release list --repo "$GITHUB_REPOSITORY" --json tagName --limit 500 \
        | jq -r '.[].tagName' \
        | grep "^${plugin_name}-" \
        | xargs -I{} gh release delete {} --repo "$GITHUB_REPOSITORY" --yes --cleanup-tag 2>/dev/null || true
    done
    rm -rf plugins
  fi
  # Reset the releases branch to a fresh orphan
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

# --- Version guard ---
# Ensure the releases branch was initialised with the current repo version.
# Skip during force rebuild — the branch is being rebuilt from scratch.
if [[ "${FORCE_REBUILD:-false}" != "true" ]]; then
  current_branch_ver=$(cat REPO_VER 2>/dev/null || echo "")
  if [[ "$current_branch_ver" != "$RELEASES_BRANCH_VERSION" ]]; then
    echo "::error::Releases branch version mismatch."
    echo "::error::  Expected : $RELEASES_BRANCH_VERSION"
    echo "::error::  Found    : ${current_branch_ver:-'(none — migration not run)'}"
    echo "::error::Run the 'Migrate Releases to GitHub Releases' workflow first, then re-run."
    exit 1
  fi
fi

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

echo "$RELEASES_BRANCH_VERSION" > REPO_VER
git add metadata manifest.json README.md REPO_VER

if git diff --cached --quiet; then
  echo "No changes to commit."
else
  # Check whether the staged diff is purely timestamp noise:
  #   README.md  - "*Last updated: ..." footer
  #   manifest.json - "generated_at" field
  # Any other changed file (e.g. a per-plugin manifest.json) counts as a real change.
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

Source commit: $source_commit${plugin_list}"

    git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" $RELEASES_BRANCH
    echo "Successfully published to ${RELEASES_BRANCH}"
  fi  # end only_timestamps check
fi
