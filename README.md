# Dispatcharr Plugin Repository

> **This is a listing and distribution repository.** Plugin development, testing, and pre-releases should happen in your own repository. Submit a PR here only when your plugin is ready for public distribution.

A repository for publishing and distributing Dispatcharr Python plugins with automated validation and release management.

## Quick Links

| Resource | Description |
|----------|-------------|
| [Browse Plugins](https://github.com/Dispatcharr/Plugins/tree/releases) | All available plugins on the releases branch |
| [Plugin Manifest](https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json) | Root plugin index with metadata and download URLs |
| [Download Releases](https://github.com/Dispatcharr/Plugins/tree/releases/zips) | Plugin ZIP files and per-plugin manifests |

## How It Works

Each plugin lives in `plugins/<plugin-name>/` and must contain a valid `plugin.json`. When a PR is merged to `main`, plugins are automatically packaged and published to the [`releases` branch](https://github.com/Dispatcharr/Plugins/tree/releases).

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

Visit the [releases branch](https://github.com/Dispatcharr/Plugins/tree/releases) to browse and download plugins, or fetch `manifest.json` programmatically:

```bash
curl https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

## Verifying Manifest Signatures

Each manifest file embeds its GPG signature directly. The `signature` field covers the compact (`jq -c '.manifest'`) form of the `manifest` payload:

```json
{
  "generated_at": "...",
  "repo_url": "...",
  "repo_name": "owner/repo",
  "signature": "-----BEGIN PGP SIGNATURE-----\n...",
  "manifest": { ... }
}
```

The public key is bundled with Dispatcharr. To verify manually, export it from the application or obtain `.github/scripts/keys/dispatcharr-plugins.pub` from the default branch.

### Steps

**1. Import the public key**

```bash
gpg --import dispatcharr-plugins.pub
```

**2. Download the manifest**

```bash
curl -sO https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

**3. Verify**

```bash
jq -c '.manifest' manifest.json | gpg --verify <(jq -r '.signature' manifest.json) -
```

A successful result looks like:

```
gpg: Signature made ...
gpg: Good signature from "..." [full]
```

The same steps apply to any per-plugin manifest - substitute the path to `zips/<plugin>/manifest.json`.