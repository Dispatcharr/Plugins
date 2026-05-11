#!/bin/bash
set -e

# aggregate-report.sh
# Combines per-plugin report fragments, posts the final PR comment,
# and optionally closes an unauthorized PR.
#
# Usage: aggregate-report.sh <pr_number> <pr_author> <plugin_count> <close_pr> <fragments_dir>
#
# Arguments:
#   pr_number      - GitHub PR number
#   pr_author      - GitHub username of PR author
#   plugin_count   - Total number of plugins validated
#   close_pr       - "true" to close the PR after posting the comment
#   fragments_dir  - Directory containing per-plugin .md fragment files
#
# Environment variables required:
#   GITHUB_REPOSITORY - Full repository name (owner/repo)
#   GH_TOKEN          - GitHub token for API access

PR_NUMBER=$1
PR_AUTHOR=$2
PLUGIN_COUNT=$3
CLOSE_PR=$4
FRAGMENTS_DIR=${5:-.}

if [[ -z "$PR_NUMBER" || -z "$PR_AUTHOR" || -z "$PLUGIN_COUNT" || -z "$CLOSE_PR" ]]; then
  echo "Usage: $0 <pr_number> <pr_author> <plugin_count> <close_pr> [fragments_dir]"
  exit 1
fi

OVERALL_FAILED=0

if [[ -n "${TITLE_VALID:-}" && "${TITLE_VALID}" != "true" ]]; then
  OVERALL_FAILED=1
fi

# Parse per-plugin report files
COMBINED_BODY=""
TABLE_HEADER="| name | version | description | author | maintainers |"
TABLE_SEP="|---|---|---|---|---|"
TABLE_ROWS=""
PLUGIN_LINKS=""

for fragment in "$FRAGMENTS_DIR"/*.fragment.md; do
  [[ -f "$fragment" ]] || continue

  # Check if fragment contains a failure marker
  if grep -q "❌" "$fragment"; then
    OVERALL_FAILED=1
  fi

  # Extract metadata table row from hidden comment marker
  META_ROW=$(grep '<!--META_ROW:' "$fragment" | sed 's/<!--META_ROW://;s/-->//' || true)
  if [[ -n "$META_ROW" ]]; then
    IFS=$'\t' read -r f_name f_version f_description f_author f_maintainers f_repo_url f_discord_thread <<< "$META_ROW"
    TABLE_ROWS+="| $f_name | $f_version | $f_description | $f_author | $f_maintainers |"$'\n'
    if [[ -n "$f_repo_url" || -n "$f_discord_thread" ]]; then
      PLUGIN_LINKS+="**\`${f_name}\`:**"$'\n'
      [[ -n "$f_repo_url" ]] && PLUGIN_LINKS+="- [GitHub Repository](${f_repo_url})"$'\n'
      [[ -n "$f_discord_thread" ]] && PLUGIN_LINKS+="- [Discord Thread](${f_discord_thread})"$'\n'
      PLUGIN_LINKS+=$'\n'
    fi
  fi

  # Strip internal marker lines from visible output
  VISIBLE=$(grep -v '<!--META_ROW:' "$fragment")
  COMBINED_BODY+="$VISIBLE"$'\n\n'
done

# Build "other plugins by this contributor" section by expanding sparse-checkout
OTHER_PLUGINS_SECTION=""
if git sparse-checkout add plugins 2>/dev/null && git checkout 2>/dev/null; then
  PR_PLUGIN_NAMES=()
  for _frag in "$FRAGMENTS_DIR"/*.fragment.md; do
    [[ -f "$_frag" ]] || continue
    _bn=$(basename "$_frag" .fragment.md)
    PR_PLUGIN_NAMES+=("$_bn")
  done

  OTHER_PLUGIN_ENTRIES=()
  for _pjson in plugins/*/plugin.json; do
    [[ -f "$_pjson" ]] || continue
    _pname=$(basename "$(dirname "$_pjson")")

    # Skip plugins that are part of this PR
    _skip=false
    for _pr_p in "${PR_PLUGIN_NAMES[@]}"; do
      [[ "$_pr_p" == "$_pname" ]] && _skip=true && break
    done
    $_skip && continue

    _p_author=$(jq -r '.author // ""' "$_pjson" 2>/dev/null || true)
    _p_maintainers=$(jq -r '[.maintainers[]?] | join(" ")' "$_pjson" 2>/dev/null || true)

    if [[ "$_p_author" == "$PR_AUTHOR" ]] || [[ " $_p_maintainers " =~ " $PR_AUTHOR " ]]; then
      _p_display_name=$(jq -r '.name // ""' "$_pjson" 2>/dev/null || echo "$_pname")
      _p_version=$(jq -r '.version // ""' "$_pjson" 2>/dev/null || true)
      _p_repo_url=$(jq -r '.repo_url // ""' "$_pjson" 2>/dev/null || true)
      if [[ -n "$_p_repo_url" ]]; then
        _p_link="$_p_repo_url"
      else
        _p_link="https://github.com/${GITHUB_REPOSITORY}/tree/${BASE_REF:-main}/plugins/${_pname}"
      fi
      _version_suffix=""
      [[ -n "$_p_version" ]] && _version_suffix="$_p_version"
      _display_link="[**${_p_display_name}**](${_p_link})"
      _slug_link="[\`${_pname}\`](https://github.com/${GITHUB_REPOSITORY}/tree/${BASE_REF:-main}/plugins/${_pname})"
      OTHER_PLUGIN_ENTRIES+=("| ${_display_link} | ${_slug_link} | ${_version_suffix} |")
    fi
  done

  if [[ ${#OTHER_PLUGIN_ENTRIES[@]} -gt 0 ]]; then
    OTHER_PLUGINS_SECTION="<details>"
    OTHER_PLUGINS_SECTION+=$'\n'
    OTHER_PLUGINS_SECTION+="<summary>Other plugins by <code>${PR_AUTHOR}</code> in this repository (${#OTHER_PLUGIN_ENTRIES[@]})</summary>"
    OTHER_PLUGINS_SECTION+=$'\n\n'
    OTHER_PLUGINS_SECTION+="| Plugin | Slug | Version |"
    OTHER_PLUGINS_SECTION+=$'\n'
    OTHER_PLUGINS_SECTION+="|--------|------|---------|"
    OTHER_PLUGINS_SECTION+=$'\n'
    for _entry in "${OTHER_PLUGIN_ENTRIES[@]}"; do
      OTHER_PLUGINS_SECTION+="${_entry}"$'\n'
    done
    OTHER_PLUGINS_SECTION+=$'\n</details>'
  fi
fi

# Build comment
{
  echo "<!--PLUGIN_VALIDATION_COMMENT-->"
  echo ""
  echo "# Plugin Validation Results"
  echo ""
  echo "**Modified plugins:** $PLUGIN_COUNT"
  echo ""

  if [[ "${CLOSE_REASON:-}" == "no-valid-plugins" ]]; then
    # echo ""
    # echo "## Invalid Plugin Folder Name"
    echo ""
    echo "⚠️ Your PR modifies plugin folder(s) whose names do not meet the naming requirements. Plugin folder names must be **lowercase letters, numbers, and hyphens only** (e.g. \`my-plugin\`). Spaces and other special characters are not allowed."
    echo ""
    echo "Please rename the folder(s) and update your PR."
    if [[ -n "${DISCORD_URL:-}" ]]; then
      echo ""
      echo "For help: [Dispatcharr Discord]($DISCORD_URL)"
    fi
  elif [[ "${CLOSE_REASON:-}" == "author-blacklisted" ]]; then
    echo ""
    echo "## PR Closed: Account Restricted"
    echo ""
    echo "Your GitHub account (\`$PR_AUTHOR\`) is not permitted to submit plugins to this repository. This PR has been automatically closed."
    if [[ -n "${DISCORD_URL:-}" ]]; then
      echo ""
      echo "If you believe this is an error, please reach out via the [Dispatcharr Discord]($DISCORD_URL)."
    fi
  elif [[ "${CLOSE_REASON:-}" == "plugin-blacklisted" ]]; then
    echo ""
    echo "## PR Closed: Plugin Restricted"
    echo ""
    echo "One or more plugins in this PR are on the restricted list and cannot be submitted to this repository. This PR has been automatically closed."
    if [[ -n "${DISCORD_URL:-}" ]]; then
      echo ""
      echo "If you believe this is an error, please reach out via the [Dispatcharr Discord]($DISCORD_URL)."
    fi
  elif [[ "$CLOSE_PR" == "true" ]]; then
    echo ""
    echo "## PR Closed: Unauthorized"
    echo ""
    echo "Your GitHub username (\`$PR_AUTHOR\`) does not appear in \`author\` or \`maintainers\` for any of the plugin(s) in this PR. This PR has been automatically closed."
    echo "If you would like to contribute to this plugin, please consider reaching out to the maintainers of this plugin on Discord, or the plugin's Github repository."
    echo ""
    echo "If you are submitting a new plugin, add your GitHub username to the \`author\` field in your \`plugin.json\`."
    if [[ -n "$PLUGIN_LINKS" ]]; then
      echo ""
      echo "### Plugin Contact Links"
      echo ""
      echo "$PLUGIN_LINKS"
    fi
    if [[ -n "${DISCORD_URL:-}" ]]; then
      echo ""
      echo "For general help or plugin discussion:"
      echo "- [Dispatcharr Discord]($DISCORD_URL)"
    fi
  else
    echo "$COMBINED_BODY"

  if [[ -n "${OUTSIDE_FILES:-}" && "${OUTSIDE_VIOLATION:-}" == "true" ]]; then
      OVERALL_FAILED=1
      echo ""
      echo "⚠️ This PR modifies files outside of \`plugins/\`, which requires write access to the repository. These changes will block merging."
      echo ""
      echo "External contributions to repository tooling and scripts are not accepted via PR. If you think something needs fixing, please [open an issue](https://github.com/${GITHUB_REPOSITORY}/issues/new/choose) instead."
      echo ""
      echo "**Modified files:**"
      echo "\`\`\`"
      echo "${OUTSIDE_FILES}"
      echo "\`\`\`"
      echo ""
      echo "Remove these changes and resubmit with only modifications inside \`plugins/\`."
      if [[ -n "${DISCORD_URL:-}" ]]; then
        echo ""
        echo "For help: [Dispatcharr Discord]($DISCORD_URL)"
      fi
      echo ""
    fi

    if [[ "${PUB_KEY_CHANGED:-}" == "true" ]]; then
      echo ""
      echo "---"
      echo ""
      echo "### ⚠️ Signing Key Change Detected"
      echo ""
      echo "This PR modifies \`.github/scripts/keys/dispatcharr-plugins.pub\`. This is the public GPG key used by Dispatcharr to verify manifest signatures."
      echo ""
      echo "**Before merging, confirm:**"
      echo "- The corresponding private key and passphrase secrets (\`GPG_PRIVATE_KEY\`, \`GPG_PASSPHRASE\`) have been updated in the repository settings."
      echo "- The new public key has been bundled into the Dispatcharr application."
      echo "- Existing embedded signatures in \`manifest.json\` files on the \`releases\` branch will be regenerated on next publish."
      echo ""
    fi

    # insert --- if there are ANY codeql/clamav findings, medium, low, or skip/unscanned notice
    if [[ -n "${CODEQL_RESULT:-}" && "${CODEQL_RESULT:-}" != "skipped" && "${CODEQL_RESULT:-}" != "success" ]] || \
       [[ -n "${CODEQL_MEDIUMS:-}" && "${CODEQL_MEDIUMS}" != "0" && "${CODEQL_RESULT:-}" != "skipped" ]] || \
       [[ -n "${CODEQL_LOWS:-}" && "${CODEQL_LOWS}" != "0" && "${CODEQL_RESULT:-}" != "skipped" ]] || \
       [[ "${CODEQL_RESULT:-}" == "skipped" && -n "${CODEQL_UNSCANNED_LANGS:-}" ]] || \
       [[ "${CODEQL_RESULT:-}" != "skipped" && -n "${CODEQL_RESULT:-}" && -n "${CODEQL_UNSCANNED_LANGS:-}" ]] || \
       [[ "${CLAMAV_RESULT:-}" == "failure" ]]; then
      echo ""
      echo "---"
      echo ""
    fi

    if [[ "${CLAMAV_RESULT:-}" == "failure" ]]; then
      OVERALL_FAILED=1
      INFECTED_LABEL="${CLAMAV_INFECTED:-unknown}"
      echo ""
      echo "❌ **ClamAV detected $INFECTED_LABEL infected file(s)**."
      echo ""
      if [[ -f "clamav-findings/clamav-findings.md" ]]; then
        cat "clamav-findings/clamav-findings.md"
      fi
    fi

    if [[ -n "${CODEQL_RESULT:-}" && "${CODEQL_RESULT:-}" != "skipped" && "${CODEQL_RESULT:-}" != "success" ]]; then
      # echo ""
      # echo "## Code Quality"
      echo ""
      OVERALL_FAILED=1
      ERROR_LABEL="${CODEQL_ERRORS:-unknown}"
      echo "❌ **CodeQL found $ERROR_LABEL high or critical issue(s)** - these must be fixed before merging."
      echo ""
      if [[ -f "codeql-findings/codeql-findings.md" ]]; then
        cat "codeql-findings/codeql-findings.md"
      fi
    fi

    if [[ -n "${CODEQL_MEDIUMS:-}" && "${CODEQL_MEDIUMS:-}" != "0" && "${CODEQL_RESULT:-}" != "skipped" ]]; then
      echo ""
      echo "**CodeQL found ${CODEQL_MEDIUMS} medium severity issue(s)**"
      echo "These are not blocking, but are included for visibility."
      echo ""
      if [[ -f "codeql-medium-findings/codeql-medium-findings.md" ]]; then
        cat "codeql-medium-findings/codeql-medium-findings.md"
      fi
    fi

    if [[ -n "${CODEQL_LOWS:-}" && "${CODEQL_LOWS:-}" != "0" && "${CODEQL_RESULT:-}" != "skipped" ]]; then
      echo ""
      echo "<details>"
      echo "<summary>CodeQL found ${CODEQL_LOWS} low severity or informational result(s)</summary>"
      echo "These are not blocking, but are included for visibility."
      echo ""
      if [[ -f "codeql-low-findings/codeql-low-findings.md" ]]; then
        cat "codeql-low-findings/codeql-low-findings.md"
      fi
      echo ""
      echo "</details>"
    fi

    # CodeQL skipped notice (when no scannable files exist but unscannable types were found)
    if [[ "${CODEQL_RESULT:-}" == "skipped" && -n "${CODEQL_UNSCANNED_LANGS:-}" ]]; then
      UNSCANNED_DISPLAY=$(echo "${CODEQL_UNSCANNED_LANGS}" | tr ',' ' ')
      echo ""
      echo "**CodeQL analysis was skipped** - no supported source files were found. The following bundled file type(s) are not covered by CodeQL: \`${UNSCANNED_DISPLAY}\`."
      echo ""
    elif [[ -n "${CODEQL_UNSCANNED_LANGS:-}" && "${CODEQL_RESULT:-}" != "skipped" && -n "${CODEQL_RESULT:-}" ]]; then
      UNSCANNED_DISPLAY=$(echo "${CODEQL_UNSCANNED_LANGS}" | tr ',' ' ')
      echo ""
      echo "**Note:** The following bundled file type(s) were not scanned by CodeQL (unsupported language): \`${UNSCANNED_DISPLAY}\`."
      echo ""
    fi

    if [[ -n "${TITLE_VALID:-}" && "${TITLE_VALID}" != "true" ]]; then
      echo ""
      echo "---"
      echo ""
      echo "### ❌ PR Title Format"
      echo ""
      echo "${TITLE_FEEDBACK}"
      if [[ -n "${TITLE_SUGGESTION:-}" ]]; then
        echo ""
        echo "**Suggested format:** \`${TITLE_SUGGESTION}\`"
      fi
      echo ""
    fi

    echo ""
    echo "---"
    echo ""
    if [[ $OVERALL_FAILED -eq 0 ]]; then
      echo "## 🎉 All validation checks passed!"
      echo ""
      echo "This PR modifies **$PLUGIN_COUNT** plugin(s) and all checks have passed."
    else
      echo "## ❌ Validation failed"
      echo ""
      echo "Some checks failed. Please review the errors above and update your PR."
    fi

    if [[ -n "$OTHER_PLUGINS_SECTION" ]]; then
      echo ""
      echo "---"
      echo ""
      echo "$OTHER_PLUGINS_SECTION"
    fi

    # if [[ -n "$PLUGIN_LINKS" ]]; then
    #   echo ""
    #   echo "---"
    #   echo ""
    #   echo "## Plugin Links"
    #   echo ""
    #   echo "$PLUGIN_LINKS"
    # fi

    # if [[ -n "$TABLE_ROWS" ]]; then
    #   echo ""
    #   echo "---"
    #   echo ""
    #   echo "## Plugin Metadata"
    #   echo ""
    #   echo "$TABLE_HEADER"
    #   echo "$TABLE_SEP"
    #   echo "$TABLE_ROWS"
    # fi
  fi
} > pr_comment.txt

# Minimize all previous validation comments as outdated before posting the new one
OWNER="${GITHUB_REPOSITORY%%/*}"
REPO="${GITHUB_REPOSITORY##*/}"

PREV_NODE_IDS=$(gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        comments(first: 100) {
          nodes { id body }
        }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO" -F number="$PR_NUMBER" \
  --jq '.data.repository.pullRequest.comments.nodes[]
        | select(.body | contains("<!--PLUGIN_VALIDATION_COMMENT-->"))
        | .id' 2>/dev/null || true)

if [[ -n "$PREV_NODE_IDS" ]]; then
  while IFS= read -r node_id; do
    gh api graphql -f query='
      mutation($id: ID!) {
        minimizeComment(input: {subjectId: $id, classifier: OUTDATED}) {
          minimizedComment { isMinimized }
        }
      }
    ' -f id="$node_id" > /dev/null 2>&1 || true
  done <<< "$PREV_NODE_IDS"
  echo "Minimized $(echo "$PREV_NODE_IDS" | wc -l | tr -d ' ') previous validation comment(s) as outdated"
fi

# Post PR comment - script succeeds/fails based on whether the comment posted
gh pr comment "$PR_NUMBER" --body "$(cat pr_comment.txt)"
COMMENT_EXIT=$?

# Close PR for unauthorized plugin modifications
if [[ "$CLOSE_PR" == "true" && ( "${CLOSE_REASON:-}" == "unauthorized" || "${CLOSE_REASON:-}" == "author-blacklisted" || "${CLOSE_REASON:-}" == "plugin-blacklisted" ) ]]; then
  gh pr close "$PR_NUMBER"
  echo "PR #$PR_NUMBER closed: unauthorized"
  exit $COMMENT_EXIT
fi

exit $COMMENT_EXIT
