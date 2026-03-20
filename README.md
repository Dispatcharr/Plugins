# Dispatcharr Plugin Repository

> **This is a listing and distribution repository.** Plugin development, testing, and pre-releases should happen in your own repository. Submit a PR here only when your plugin is ready for public distribution.

A repository for publishing and distributing Dispatcharr Python plugins with automated validation and release management.

## Quick Links

| Resource | Description |
|----------|-------------|
| [Browse Plugins](https://github.com/sethwv/sample-plugin-repo/tree/releases) | All available plugins on the releases branch |
| [Plugin Manifest](https://raw.githubusercontent.com/sethwv/sample-plugin-repo/releases/manifest.json) | Plugin metadata, checksums, and download URLs |
| [Download Releases](https://github.com/sethwv/sample-plugin-repo/tree/releases/releases) | Plugin ZIP files |
| [View Metadata](https://github.com/sethwv/sample-plugin-repo/tree/releases/metadata) | Version metadata with commit info and checksums |

## How It Works

Each plugin lives in `plugins/<plugin-name>/` and must contain a valid `plugin.json`. When a PR is merged to `main`, plugins are automatically packaged and published to the [`releases` branch](https://github.com/sethwv/sample-plugin-repo/tree/releases).

### PR Validation

Every PR runs automated validation that checks:

- Folder name is lowercase-kebab-case
- `plugin.json` is valid and contains required fields
- Version is incremented for existing plugins
- PR author is listed in `author` or `maintainers`
- `.github/` files are not modified by non-maintainers
- Python code is scanned by CodeQL (required check)

PRs where the author has no permission for any modified plugin are automatically closed with instructions.

Results are posted as a comment on the PR.

### Publishing

On merge to `main`, each plugin is:

- Packaged into a versioned ZIP (`plugin-name-1.0.0.zip`) and a latest ZIP (`plugin-name-latest.zip`)
- Given an MD5 checksum
- Listed in `manifest.json` with download URLs and metadata
- Only the 10 most recent versioned ZIPs are kept per plugin

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including the `plugin.json` spec, validation rules, and what happens after merge.

## Downloading Plugins

Visit the [releases branch](https://github.com/sethwv/sample-plugin-repo/tree/releases) to browse and download plugins, or fetch `manifest.json` programmatically:

```bash
curl https://raw.githubusercontent.com/sethwv/sample-plugin-repo/releases/manifest.json
```