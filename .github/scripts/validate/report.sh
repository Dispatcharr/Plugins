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

    if [[ -n "${OUTSIDE_FILES:-}" ]]; then
      OVERALL_FAILED=1
      echo ""
      echo "⚠️ This PR modifies files outside of \`plugins/\`, which requires write access to the repository. These changes will block merging."
      echo ""
      echo "**Modified files:**"
      echo "\`\`\`"
      echo "${OUTSIDE_FILES}"
      echo "\`\`\`"
      echo ""
      echo "Please remove these changes and resubmit with only modifications inside \`plugins/\`."
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

    CODEQL_SCAN_URL="https://github.com/${GITHUB_REPOSITORY}/security/code-scanning?query=is%3Aopen+pr%3A${PR_NUMBER}"
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
      echo "**CodeQL found ${CODEQL_MEDIUMS} medium severity issue(s)** - these are not blocking but are worth a look."
      echo ""
      if [[ -f "codeql-medium-findings/codeql-medium-findings.md" ]]; then
        cat "codeql-medium-findings/codeql-medium-findings.md"
      fi
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

# Post PR comment - script succeeds/fails based on whether the comment posted
gh pr comment "$PR_NUMBER" --body "$(cat pr_comment.txt)"
COMMENT_EXIT=$?

# Close PR for unauthorized plugin modifications
if [[ "$CLOSE_PR" == "true" && "${CLOSE_REASON:-}" == "unauthorized" ]]; then
  gh pr close "$PR_NUMBER"
  echo "PR #$PR_NUMBER closed: unauthorized"
  exit $COMMENT_EXIT
fi

exit $COMMENT_EXIT
