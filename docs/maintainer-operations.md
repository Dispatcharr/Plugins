# Maintainer operations

This guide covers repository settings and workflows that maintainers operate. Configure settings in **Settings → Secrets and variables → Actions**. Do not place private keys, webhook URLs, or other credentials in repository variables, workflow files, issues, or pull requests.

## Required secrets and variables

| Setting | Type | Used for |
| --- | --- | --- |
| `GH_APP_ID` | Variable | GitHub App ID used to mint workflow tokens. |
| `GH_APP_PRIVATE_KEY` | Secret | GitHub App private key. |
| `GPG_PRIVATE_KEY` | Secret | Armored private key used to sign published manifests. |
| `GPG_PASSPHRASE` | Secret | Passphrase for `GPG_PRIVATE_KEY`. |

The GitHub App must be installed on this repository with the permissions needed by the workflows, including repository contents, pull requests, and issues. The shared [GitHub App token action](../.github/actions/gh-app-token/action.yml) falls back to `GITHUB_TOKEN` when the App settings are absent. That fallback cannot auto-merge or reliably trigger downstream publishing, so configure the App for normal operations.

Generate a new manifest-signing key with:

```bash
.github/scripts/keys/generate-signing-key.sh
```

Store the generated private key and passphrase only as the two repository secrets. Commit the generated public key at `.github/scripts/keys/dispatcharr-plugins.pub`, and update the public key bundled by Dispatcharr before using the new key to publish manifests. Rotate the signing key deliberately because clients use the bundled public key to verify manifests.

## Optional settings

| Setting | Type | Purpose |
| --- | --- | --- |
| `AUTHOR_BLACKLIST` | Variable | Comma-separated GitHub logins blocked from plugin submission validation. |
| `PLUGIN_BLACKLIST` | Variable | Comma-separated plugin slugs blocked from validation. |
| `AUTO_MERGE_UPDATES` | Variable | Set to `true` to enable eligible plugin-update auto-merges. |
| `AUTO_MERGE_BLACKLIST` | Variable | Comma-separated GitHub logins excluded from auto-merge only. |
| `AUTO_MERGE_AUTHOR_LIMIT` | Variable | Maximum automatic merges per author in the rate window. Defaults to `4`. Set to `0` or less to disable this limit. |
| `AUTO_MERGE_PLUGIN_LIMIT` | Variable | Maximum automatic merges per plugin in the rate window. Defaults to `4`. Set to `0` or less to disable this limit. |
| `AUTO_MERGE_RATE_WINDOW_HOURS` | Variable | Rolling rate-limit window in hours. Defaults to `24` and must be greater than zero. |
| `WEBHOOK_URL` | Variable | Destination for signed generic webhook events. Requires `WEBHOOK_SECRET`. |
| `WEBHOOK_SECRET` | Secret | HMAC secret for generic webhook events. Requires `WEBHOOK_URL`. |
| `DISCORD_WEBHOOKS` | Secret | JSON map of Discord webhook routes. See [webhooks](webhooks.md). |
| `DISCORD_URL` | Variable | Dispatcharr Discord URL included in validation output. |
| `EXTERNAL_README_REPO` | Variable | Target repository for the optional external README update workflow. |
| `EXTERNAL_README_PATH` | Variable | Target README path for that workflow. |
| `PR_REVIEWER` | Variable | Optional reviewer requested by the external README update workflow. |

Webhook delivery is opt-in and best-effort. See [webhooks](webhooks.md) for event formats and Discord routing. The external README workflow skips itself when its required GitHub App and target settings are absent.

## Auto-merge

`Auto-merge Plugin Updates` runs after a successful `Validate Plugin` workflow. It only squash-merges a non-draft pull request when all of these conditions hold:

1. `AUTO_MERGE_UPDATES` is exactly `true`.
2. A GitHub App token is available.
3. The pull request has the `Plugin Update` label, is cleanly mergeable, and has none of these labels: `New Plugin`, `Repo Update`, `Invalid`, `QUARANTINE`, or `Manual Review Required`.
4. Its diff changes only existing plugins under `plugins/`.
5. Its author is not in `AUTO_MERGE_BLACKLIST` and the author and plugin are within the configured rate limits.

Every skipped candidate is marked for manual review. Successful automatic merges receive the `Auto Merged` label. Configure the repository’s branch protection and GitHub App permissions so the App can squash-merge eligible pull requests and its resulting push can start publication.

## Maintainer workflows

| Workflow | When to use it | Notes |
| --- | --- | --- |
| **Publish Plugins** | Publishes plugin releases after changes reach `main`, or rebuilds releases manually. | A full rebuild is destructive. Manual rebuilds require `force_rebuild_confirm` to be `CONFIRM`. Target one plugin with `force_rebuild_plugin` whenever possible. |
| **Yank Plugin Version** | Removes a published version following a Version Removal Request. | Requires the plugin slug, version, and authorizing issue number. It updates releases and closes the request. |
| **Run Migrations** | Performs maintainer-directed repository or release-branch migrations. | Review workflow inputs and logs before running it. |
| **Update External README** | Synchronizes documentation to the configured external repository. | It is inactive until the optional external-README settings are configured. |

Before changing workflows, test, review, or signing configuration, verify that the GitHub App still has the required access and that publishing, validation, and auto-merge can create their expected labels, commits, and pull requests.
