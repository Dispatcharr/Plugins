# Contributing to the Dispatcharr Plugin Repository

> **This is a listing and distribution repository, not a development environment.**
> Build, test, and iterate on your plugin in your own repository. Pre-releases, work-in-progress versions, and experiments belong there too. Only submit a PR here when your plugin is stable and ready for public distribution.

## Before You Start

- Build and test your plugin in your own repository first
- Ensure your plugin is stable - this repo is for public releases, not pre-releases or experiments
- You must own the rights to distribute it under an OSI-approved open source license
- Each plugin lives in its own folder under `plugins/<plugin-name>/`

## Folder Structure

```
plugins/
  your-plugin-name/
    plugin.json       # required
    main.py           # your plugin's entry point
    ...               # any other Python files, assets, or subdirectories
    README.md         # optional but recommended
    logo.png          # optional; displayed in the plugin browser
```

All files inside your plugin folder - `main.py`, helper modules, assets, subdirectories - are automatically packaged into a ZIP on merge. There is no separate build step.

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
| `repo_url` | `string` | URL to the plugin's source repository (must start with `http://` or `https://`) |
| `discord_thread` | `string` | URL to the associated Discord thread (must start with `http://` or `https://`) |
| `deprecated` | `boolean` | Marks the plugin as deprecated. Default: `false` |
| `unlisted` | `boolean` | Excludes the plugin from the root `manifest.json` (and the releases README) but still generates a per-plugin manifest. Default: `false` |

### Full Example

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
| CodeQL | Python code is scanned for security issues (blocking) |
| `.github/` | Cannot be modified by non-maintainers of this repository |

PRs where the author has no permission for any of the modified plugins are **automatically closed** with instructions.

## What Happens After Merge

Once your PR merges to `main`, the publish workflow runs automatically:

1. Your plugin is packaged into a versioned ZIP (`your-plugin-1.0.0.zip`) and a latest ZIP (`your-plugin-latest.zip`)
2. MD5 and SHA256 checksums are computed
3. A per-plugin `zips/your-plugin-name/README.md` is generated with download links and version history
4. `manifest.json` is updated with your plugin's metadata and download URLs
5. The releases branch README is regenerated
6. Up to 10 versioned ZIPs are retained; older ones are pruned

Everything is pushed to the [`releases` branch](https://github.com/Dispatcharr/Plugins/tree/releases).

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

All other fields - including `name`, `author`, `license`, and any code changes - require a version bump.

## Licensing

All plugins must be distributed under an [OSI-approved open source license](https://opensource.org/licenses). The `license` field is required in `plugin.json` and must be a valid [SPDX identifier](https://spdx.org/licenses/).
