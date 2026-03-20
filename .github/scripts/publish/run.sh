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

# Create temporary working directory
WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

echo "Cloning repository..."
git clone --no-checkout "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$WORK_DIR/repo"
cd "$WORK_DIR/repo"

# Configure git
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# Checkout or create releases branch
echo "Setting up $RELEASES_BRANCH branch..."
if git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
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

mkdir -p releases

# --- Phases ---
echo ""
echo "=== Building ZIPs ==="
bash "$SCRIPT_DIR/build-zips.sh"

echo ""
echo "=== Generating per-plugin READMEs ==="
bash "$SCRIPT_DIR/plugin-readmes.sh"

echo ""
echo "=== Cleaning up old releases ==="
bash "$SCRIPT_DIR/cleanup.sh"

echo ""
echo "=== Generating manifests ==="
bash "$SCRIPT_DIR/generate-manifest.sh"

echo ""
echo "=== Generating releases README ==="
bash "$SCRIPT_DIR/releases-readme.sh"

# --- Commit and push ---
echo ""
echo "=== Committing ==="
rm -rf plugins
git rm -rf --cached plugins 2>/dev/null || true
git add releases metadata manifest.json README.md

if git diff --cached --quiet; then
  echo "No changes to commit."
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
  echo "Successfully published to $RELEASES_BRANCH"
fi
