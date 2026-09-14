# Contributing to the Dispatcharr Plugin Repository

> **This is a listing and distribution repository, not a development environment.**
> Build, test, and iterate on your plugin in your own repository. Pre-releases, work-in-progress versions, and experiments belong there too. Only submit a PR here when your plugin is stable and ready for public distribution.

## Before You Start

- Build and test your plugin in your own repository first
- Ensure your plugin is stable - this repo is for public releases, not pre-releases or experiments
- You must own the rights to distribute it under an OSI-approved open source license
- Each plugin lives in its own folder under `plugins/<plugin-name>/`

## Folder Structure

### External plugin (recommended)

If your plugin has its own GitHub repository, submit a directory with only a `plugin.json`. The registry fetches your ZIP on each version bump from your upstream release URL.

```
plugins/
  your-plugin-name/
    plugin.json       # required; includes source_type and source_url
    README.md         # optional but recommended
    logo.png          # optional; displayed in the plugin browser
```

On merge, the registry downloads the ZIP from your `source_url`, computes its checksums independently, re-hosts it as a GitHub Release on this registry, and GPG-signs the manifest. Clients always download from the registry, never directly from your upstream URL.

**Requirements for external plugins:**

- `source_url` must be an HTTPS URL pointing directly to a downloadable ZIP
- `source_url` must contain a `{version}` placeholder that is substituted at publish time
- `repo_url` is required (points to your source repository)
- The source repository must be public and under an OSI-approved open source license

Each version bump requires a PR to this repository (updating `version` in `plugin.json`), which must be approved and merged before anything is published. How you automate or manage that is up to you.

### Standard plugin (full source)

For simple scripts or plugins without their own repository or build process.

```
plugins/
  your-plugin-name/
    plugin.json       # required
    main.py           # your plugin's entry point
    ...               # any other Python files, assets, or subdirectories
    README.md         # optional but recommended
    logo.png          # optional; displayed in the plugin browser
```

Everything in your plugin folder (`main.py`, helper modules, assets, subdirectories) is automatically packaged into a ZIP on merge. No separate build step.

Plugin folder names must be **lowercase-kebab-case** (e.g. `my-plugin-name`).

## Submitting a Plugin

1. Fork this repository and create a branch
2. Create your plugin folder under `plugins/your-plugin-name/`
3. Add a valid `plugin.json` (see spec below)
4. Optionally add a `README.md` and `logo.png`
5. Submit a pull request to `main`

### PR Title Format

PR titles must follow this format (the colon after `]` is optional):

| Scenario | Format | Example |
|----------|--------|---------|
| Single plugin changed | `[plugin-slug] description` | `[my-plugin] Bump version to 1.2.0` |
| Multiple plugins changed | `[your-github-username] description` | `[sethwv] Update my plugins to new manifest formatting` |
| Repo/script changes (maintainers only) | `[repo] description` | `[repo] Add new validation rules for PRs` |

The plugin slug is the folder name under `plugins/` (e.g. `my-plugin-name`). Validation checks the title automatically; renaming the PR triggers a re-run.

For **updates**, increment the version in `plugin.json` - the validation workflow enforces this. Exception: some metadata-only fields (`description`, `repo_url`, `discord_thread`, `maintainers`, `min_dispatcharr_version`, `max_dispatcharr_version`, `deprecated`, `unlisted`) can be updated without a version bump.

## `plugin.json` Spec

### Required Fields

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "A brief description of what the plugin does",
  "author": "your-github-username",
  "license": "MIT"
}
```

| Field | Description |
|-------|-------------|
| `name` | Display name of the plugin |
| `version` | Semantic version (`MAJOR.MINOR.PATCH`) |
| `description` | Short description shown in the plugin browser |
| `author` | Your GitHub username. Used for PR permission checks - must match the GitHub account submitting the PR |
| `license` | An [OSI-approved SPDX license identifier](https://spdx.org/licenses/) (e.g. `MIT`, `Apache-2.0`, `GPL-3.0-only`) |

At least one of `author` or `maintainers` must include your GitHub username. `author` is also part of the Dispatcharr plugin spec - it is used by this repository to determine who is permitted to submit PRs for a given plugin.

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `maintainers` | `string[]` | Additional GitHub usernames permitted to submit PRs for this plugin (in addition to `author`) |
| `min_dispatcharr_version` | `string` | Minimum Dispatcharr version required (e.g. `v0.19.0` or `0.19.0`) |
| `max_dispatcharr_version` | `string` | Maximum Dispatcharr version supported. Must be ≥ `min_dispatcharr_version` if both are set |
| `repo_url` | `string` | URL to the plugin's source repository (must start with `http://` or `https://`). Required for external plugins |
| `discord_thread` | `string` | URL to the associated Discord thread (must start with `http://` or `https://`) |
| `deprecated` | `boolean` | Marks the plugin as deprecated. Default: `false` |
| `unlisted` | `boolean` | Excludes the plugin from the root `manifest.json` (and the releases README) but still generates a per-plugin manifest. Default: `false` |
| `source_type` | `string` | Set to `"external"` to declare this as an external plugin. Omit (or `"local"`) for standard plugins |
| `source_url` | `string` | Required when `source_type` is `"external"`. Must be a GitHub Releases URL containing a `{version}` placeholder, e.g. `https://github.com/owner/repo/releases/download/v{version}/plugin.zip` |

### Full Example (external plugin, recommended)

```json
{
  "name": "My Plugin",
  "version": "1.2.0",
  "description": "Does something useful for Dispatcharr",
  "author": "your-github-username",
  "license": "MIT",
  "source_type": "external",
  "source_url": "https://github.com/your-github-username/my-plugin/releases/download/v{version}/my-plugin.zip",
  "repo_url": "https://github.com/your-github-username/my-plugin",
  "discord_thread": "https://discord.com/channels/..."
}
```

### Full Example (standard plugin)

```json
{
  "name": "My Plugin",
  "version": "1.2.0",
  "description": "Does something useful for Dispatcharr",
  "author": "your-github-username",
  "maintainers": ["collaborator-username"],
  "license": "MIT",
  "min_dispatcharr_version": "v0.19.0",
  "repo_url": "https://github.com/your-github-username/my-plugin",
  "discord_thread": "https://discord.com/channels/..."
}
```

## What Happens When You Open a PR

Automated validation runs on every PR and posts a comment with results. The following checks must all pass before a PR can merge:

| Check | Details |
|-------|---------|
| Folder name | Must be lowercase-kebab-case |
| `plugin.json` presence | File must exist |
| JSON syntax | Must be valid JSON |
| Required fields | `name`, `version`, `description`, `author` or `maintainers`, `license` |
| Version format | Must be `MAJOR.MINOR.PATCH` (semver) |
| Version bump | Must be greater than the current published version (see [metadata-only exceptions](#versioning)) |
| Permission | PR author must be listed in `author` or `maintainers` |
| License | Must be a valid OSI-approved SPDX identifier |
| `min_dispatcharr_version` | Must be semver if provided |
| `max_dispatcharr_version` | Must be semver and ≥ `min_dispatcharr_version` if both provided |
| `repo_url` / `discord_thread` | Must start with `http://` or `https://` if provided |
| CodeQL | Python code is scanned for security issues (blocking). For external plugins, the release ZIP is downloaded and its contents scanned |
| ClamAV | All submitted files are scanned for malware (blocking). For external plugins, the release ZIP is downloaded and scanned |
| `source_url` | For external plugins: must be an HTTPS URL with a `{version}` placeholder; artifact must be reachable |
| `repo_url` | Required for external plugins |
| `.github/` | Cannot be modified by non-maintainers of this repository |

PRs where the author has no permission for any of the modified plugins are **automatically closed** with instructions. PRs from accounts or plugins on the repository blocklist are also automatically closed.

## What Happens After Merge

Once your PR merges to `main`, the publish workflow runs automatically:

**External plugins:**
1. The ZIP is downloaded from your `source_url` (with `{version}` substituted)
2. MD5 and SHA256 checksums are computed by the registry's infrastructure (not trusted from upstream)
3. The ZIP is published as a **GitHub Release** on this registry (tag: `your-plugin-1.0.0`); a `-latest` alias release is also maintained
4. `manifest.json` is updated with checksums and download URLs pointing to the GitHub Release assets; `source_url` pointing to the upstream release is also recorded
5. A per-plugin `README.md` is generated with download links and version history
6. Up to 10 versioned releases are retained; older ones are pruned

**Standard plugins:**
1. Your plugin is packaged into a versioned ZIP
2. MD5 and SHA256 checksums are computed
3. The ZIP is published as a **GitHub Release** on this registry (tag: `your-plugin-1.0.0`); a `-latest` alias release is also maintained
4. `manifest.json` on the releases branch is updated with metadata and download URLs pointing to the GitHub Release assets
5. A per-plugin `README.md` is generated with download links and version history
6. Up to 10 versioned releases are retained; older ones are pruned

Manifests and READMEs are committed to the [`releases` branch](https://github.com/Dispatcharr/Plugins/tree/releases). ZIP files are stored as [GitHub Release assets](https://github.com/Dispatcharr/Plugins/releases).

## Versioning

Plugins use [semantic versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- **PATCH** - bug fixes, minor tweaks
- **MINOR** - new features, backwards compatible
- **MAJOR** - breaking changes

Version increments are enforced by the validation workflow. You cannot submit a PR with the same or lower version than the currently published plugin.

**Metadata-only updates** are an exception - the following fields can be changed without bumping the version:

- `description`
- `repo_url`
- `discord_thread`
- `maintainers`
- `min_dispatcharr_version`
- `max_dispatcharr_version`
- `deprecated`
- `unlisted`

All other fields - including `name`, `author`, `license`, `source_url`, `source_type`, and any code changes - require a version bump.

> **Changing the license?** A version bump is required because the license you publish under is binding for that release. Users who installed the previous version hold rights under the old license and those cannot be revoked. The new version carries the new license going forward.

## Licensing

All plugins must be distributed under an [OSI-approved open source license](https://opensource.org/licenses). The `license` field is required in `plugin.json` and must be a valid [SPDX identifier](https://spdx.org/licenses/).

By submitting a PR you confirm that you have the rights to distribute the plugin under the license you specify. This is binding for the version being published. Users who downloaded a version hold rights under its license permanently - those rights are not affected if the version is later removed from the registry. To change the license going forward, bump the version. The old version stays under its original license.

## Version Removal

Plugin authors and maintainers can request that a specific version be removed from the registry. Reasons might include a critical bug, a security issue, a mistaken publish, or a license correction.

To request a removal, [open an issue](../../issues/new/choose) using the **Version Removal Request** template. A maintainer will run the yank workflow on your behalf.

What happens when a version is yanked:

- The GitHub Release and its asset are deleted; the manifest entry is removed from the releases branch.
- If it was the latest version, the previous version is automatically promoted to latest and a PR is opened against the source branch to roll back `plugin.json` to match.
- If it was the only version, the plugin is fully removed from the registry and a PR is opened to remove its source folder.
- Users who already downloaded the version are unaffected.
