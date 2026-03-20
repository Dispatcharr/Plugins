#!/bin/bash
set -e

# retract-plugin.sh
# Removes a plugin (or a specific version) from the releases branch
#
# Usage: retract-plugin.sh <plugin_name> [version]
#
# Arguments:
#   plugin_name - Plugin folder name (e.g. my-plugin)
#   version     - Optional: specific version to retract (e.g. 1.2.3)
#                 If omitted, all versions are retracted.
#
# Environment variables required:
#   GITHUB_REPOSITORY - Full repository name (owner/repo)
#   GITHUB_TOKEN      - GitHub token with write access

PLUGIN_NAME=$1
VERSION=$2

if [[ -z "$PLUGIN_NAME" ]]; then
  echo "Usage: $0 <plugin_name> [version]"
  exit 1
fi

# Input validation - prevent path traversal and shell injection
if [[ ! "$PLUGIN_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "Error: plugin_name must be lowercase-kebab-case (got '${PLUGIN_NAME}')"
  exit 1
fi

if [[ -n "$VERSION" && ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must be semver X.Y.Z (got '${VERSION}')"
  exit 1
fi

RELEASES_BRANCH="releases"

echo "Retracting plugin: $PLUGIN_NAME${VERSION:+ v$VERSION}"

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

git clone --no-checkout "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "$TMPDIR/repo"
cd "$TMPDIR/repo"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

if ! git ls-remote --exit-code --heads origin $RELEASES_BRANCH >/dev/null 2>&1; then
  echo "Error: releases branch does not exist"
  exit 1
fi

git checkout $RELEASES_BRANCH
git pull origin $RELEASES_BRANCH

if [[ -n "$VERSION" ]]; then
  # Retract a specific version
  ZIP_FILE="releases/$PLUGIN_NAME/${PLUGIN_NAME}-${VERSION}.zip"
  META_FILE="metadata/$PLUGIN_NAME/${PLUGIN_NAME}-${VERSION}.json"

  if [[ ! -f "$ZIP_FILE" ]] && [[ ! -f "$META_FILE" ]]; then
    echo "Error: version $VERSION of plugin '$PLUGIN_NAME' not found on $RELEASES_BRANCH branch"
    exit 1
  fi

  rm -f "$ZIP_FILE" "$META_FILE"
  echo "Removed: $ZIP_FILE"

  # Update latest.zip to point to the next most recent remaining version
  NEXT_ZIP=$(ls -1 "releases/$PLUGIN_NAME/${PLUGIN_NAME}"-*.zip 2>/dev/null \
    | grep -v '\-latest\.zip' | sort -V -r | head -1 || true)
  if [[ -n "$NEXT_ZIP" ]]; then
    cp "$NEXT_ZIP" "releases/$PLUGIN_NAME/${PLUGIN_NAME}-latest.zip"
    echo "Updated latest.zip -> $(basename "$NEXT_ZIP")"
  else
    rm -f "releases/$PLUGIN_NAME/${PLUGIN_NAME}-latest.zip"
    echo "No remaining versions - removed latest.zip"
  fi

  # Remove this version from the manifest
  if [[ -f manifest.json ]]; then
    jq --arg slug "$PLUGIN_NAME" --arg version "$VERSION" '
      .plugins |= map(
        if .slug == $slug then
          .versions |= map(select(.version != $version))
        else .
        end
      )' manifest.json > manifest.tmp && mv manifest.tmp manifest.json
  fi

  COMMIT_MSG="Retract $PLUGIN_NAME v$VERSION"

else
  # Retract all versions of the plugin
  if [[ ! -d "releases/$PLUGIN_NAME" ]] && [[ ! -d "metadata/$PLUGIN_NAME" ]]; then
    echo "Error: plugin '$PLUGIN_NAME' not found on $RELEASES_BRANCH branch"
    exit 1
  fi

  rm -rf "releases/$PLUGIN_NAME" "metadata/$PLUGIN_NAME"
  echo "Removed releases/$PLUGIN_NAME and metadata/$PLUGIN_NAME"

  # Remove plugin from the manifest entirely
  if [[ -f manifest.json ]]; then
    jq --arg slug "$PLUGIN_NAME" '
      .plugins |= map(select(.slug != $slug))' manifest.json > manifest.tmp && mv manifest.tmp manifest.json
  fi

  COMMIT_MSG="Retract plugin: $PLUGIN_NAME (all versions)"
fi

git add -A
git commit -m "$COMMIT_MSG"
git push origin $RELEASES_BRANCH

echo "Successfully retracted $PLUGIN_NAME${VERSION:+ v$VERSION} from $RELEASES_BRANCH branch"
