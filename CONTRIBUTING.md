> [!CAUTION]
> The repository's workflows recently changed. Please bear with us while we work through expected issues and hiccups. [Report a workflow issue](https://github.com/Dispatcharr/Plugins/issues/new?template=repo-issue.yml).

# Contributing

This repository is a public plugin registry, not a plugin development environment. Build, test, and iterate in your own repository. Open a pull request here when a stable version is ready for distribution.

## Before you begin

- Test the plugin with Dispatcharr.
- Confirm you have the right to distribute it under an [OSI-approved open source license](https://opensource.org/licenses).
- Decide whether the registry should package source here or retrieve a release ZIP from your own repository.
- Confirm the submission meets the [Code of Conduct](CODE_OF_CONDUCT.md) contribution boundaries.

## Choose a submission type

| Choose this | When | What you add here |
| --- | --- | --- |
| **External plugin** | The plugin has its own public source repository and release ZIPs. Recommended. | `plugin.json`, plus an optional README and logo. |
| **Standard plugin** | The plugin is small or has no separate release process. | `plugin.json` and all source files, plus an optional README and logo. |

Every plugin directory is `plugins/<plugin-slug>/`. The slug must use lowercase letters, numbers, and hyphens, such as `my-plugin`.

### External plugin

```text
plugins/
  my-plugin/
    plugin.json
    README.md          # optional
    logo.png           # optional
```

Set `source_type` to `"external"`. `source_url` must be an HTTPS URL for a downloadable ZIP and include `{version}`, which the registry replaces when it publishes. `repo_url` is required and should point to the public source repository.

On merge, the registry downloads the release ZIP, calculates its checksums, scans it, publishes it as a release in this repository, and records the upstream source URL in signed metadata. Clients download from this registry, not directly from the upstream URL.

### Standard plugin

```text
plugins/
  my-plugin/
    plugin.json
    main.py            # example entry point
    helpers.py         # other source files and assets are allowed
    README.md          # optional
    logo.png           # optional
```

The registry packages the entire plugin directory after merge. A standard plugin must include at least one source file in addition to metadata and the optional README or logo.

## Create `plugin.json`

Start with the required fields:

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "A brief description of what the plugin does",
  "author": "your-github-username",
  "license": "MIT"
}
```

| Field | Required | Description |
| --- | --- | --- |
| `name` | Yes | Plugin display name. |
| `version` | Yes | Three-segment version in `MAJOR.MINOR.PATCH` form. |
| `description` | Yes | Short browser description. |
| `author` | Yes, unless `maintainers` is supplied | GitHub username allowed to update the plugin. |
| `license` | Yes | OSI-approved SPDX identifier, such as `MIT` or `Apache-2.0`. |
| `maintainers` | No | Additional GitHub usernames allowed to update the plugin. |
| `min_dispatcharr_version` | No | Minimum supported Dispatcharr version, with optional `v` prefix. |
| `max_dispatcharr_version` | No | Maximum supported Dispatcharr version. It cannot be lower than `min_dispatcharr_version`. |
| `repo_url` | No, except external plugins | Source repository URL beginning with `http://` or `https://`. |
| `discord_thread` | No | Associated Discord thread URL beginning with `http://` or `https://`. |
| `deprecated` | No | Boolean that marks the plugin as deprecated. Defaults to `false`. |
| `unlisted` | No | Boolean that omits the plugin from the root manifest and releases README. Defaults to `false`. |
| `source_type` | No | Use `"external"` for an external plugin. Omit it or use `"local"` for a standard plugin. |
| `source_url` | Required for external plugins | HTTPS ZIP URL containing `{version}`. |

At least one of `author` or `maintainers` must name the GitHub account opening the pull request. For an existing plugin, the account must already be listed in the version on the base branch unless it has repository write permission.

### External example

```json
{
  "name": "My Plugin",
  "version": "1.2.0",
  "description": "Does something useful for Dispatcharr",
  "author": "your-github-username",
  "license": "MIT",
  "source_type": "external",
  "source_url": "https://github.com/your-github-username/my-plugin/releases/download/v{version}/my-plugin.zip",
  "repo_url": "https://github.com/your-github-username/my-plugin"
}
```

## Issues and support

Use this repository's issue tracker for registry matters: validation or publishing workflow problems, submission-process issues, repository tooling, and documentation errors. [Report a repository issue](https://github.com/Dispatcharr/Plugins/issues/new?template=repo-issue.yml).

Do not use it for bugs, compatibility problems, support requests, or feature requests for a specific plugin. Use the plugin's own source repository, linked in its `plugin.json`, or its thread in the [Dispatcharr Discord](https://discord.gg/Sp45V5BcxU).

To remove a published plugin version from the registry, [submit a Version Removal Request](https://github.com/Dispatcharr/Plugins/issues/new?template=version-removal-request.yml).

## Submit the pull request

1. Fork this repository and create a branch.
2. Add or update `plugins/<plugin-slug>/`.
3. Confirm `plugin.json` is valid JSON and the source ZIP is publicly reachable if the plugin is external.
4. Open a pull request against `main`.
5. Read the validation comment and address any reported failures.

Use one of these pull request title formats. A colon after `]` is optional.

| Change | Title format | Example |
| --- | --- | --- |
| One plugin | `[plugin-slug] description` | `[my-plugin] Bump version to 1.2.0` |
| Multiple plugins | `[github-username] description` | `[sethwv] Update my plugins` |
| Registry changes, maintainers only | `[repo] description` | `[repo] Update validation rules` |

Use of the pull request template is optional, but every pull request must include a meaningful description. A blank or materially incomplete description may result in auto-merge privileges being revoked. If you submit pull requests through automation, consider configuring it to include a link to the relevant changelog, release notes, or other change summary.

### Automatic merging

Automatic merging is not guaranteed. It only considers cleanly mergeable, non-draft updates to existing plugins that change files only under `plugins/` and pass validation. New plugins, repository changes, mixed changes, validation failures, security findings, and pull requests marked for manual review require maintainer review.

By default, automatic merging is limited to four updates per author and four updates per plugin in a rolling 24-hour period. Maintainers may change these limits, exclude authors from automatic merging, or require review for any pull request. A successful automatic merge receives the `Auto Merged` label.

## What validation checks

The workflow verifies the folder name, `plugin.json` presence and syntax, required metadata, three-segment version format, author or maintainer permission, license, Dispatcharr version constraints, optional URL fields, and external-plugin requirements. It also verifies that an external ZIP can be reached.

CodeQL scans submitted code for security findings. ClamAV scans submitted files and, for external plugins, the downloaded release ZIP. CodeQL capability and sandbox findings are reviewed by maintainers and prevent automatic merging. See [plugin security](docs/plugin-security.md) for checks and suppressions.

Only repository maintainers may change `.github/`. Pull requests from blocked authors or for blocked plugins are closed automatically. A pull request whose author cannot modify any changed plugin is also closed automatically.

## Versioning updates

Use a three-segment version in `MAJOR.MINOR.PATCH` form. We recommend following [semantic versioning](https://semver.org/): increment PATCH for fixes, MINOR for backward-compatible features, and MAJOR for breaking changes.

An existing plugin needs a higher version for source changes or most metadata changes. These fields may change without a version bump:

- `description`
- `repo_url`
- `discord_thread`
- `maintainers`
- `min_dispatcharr_version`
- `max_dispatcharr_version`
- `deprecated`
- `unlisted`

Changing `name`, `author`, `license`, `source_type`, `source_url`, or any source file requires a version bump. A license change creates a new release under the new license. It does not alter rights already granted by earlier releases.

## After merge

The registry publishes a versioned ZIP and a `-latest` alias GitHub Release, calculates MD5 and SHA256 checksums, updates signed manifests, and generates a plugin README on the [`releases` branch](https://github.com/Dispatcharr/Plugins/tree/releases). It keeps the ten newest versioned releases for each plugin.

## Remove a published version

To request removal of a version, open a [Version Removal Request](https://github.com/Dispatcharr/Plugins/issues/new?template=version-removal-request.yml). A maintainer runs the yank workflow. If the removed version was latest, the prior version becomes latest. If it was the only version, the plugin is removed from the registry. Existing downloads are unaffected.
