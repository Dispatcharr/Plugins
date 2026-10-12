# Dispatcharr Plugin Repository

> **This is a listing and distribution repository.** Plugin development, testing, and pre-releases should happen in your own repository. Submit a PR here only when your plugin is ready for public distribution.

> AI tools are used in the development of this project and repo, as well as many of the plugins included in this repo. The team personally audits and reviews every line of workflow and script generated, and all changes are tested extensively by humans. The involvement of these tools greatly increases  development velocity (nice, buzzword) and greatly assists especially where boilerplate and documentation (which we all loathe writing) are involved.


## Quick Links

| Resource | Description |
|----------|-------------|
| [Browse Plugins](https://github.com/Dispatcharr/Plugins/tree/releases) | Manifests and READMEs on the releases branch |
| [Plugin Manifest](https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json) | Root plugin index with metadata and download URLs |
| [Download Releases](https://github.com/Dispatcharr/Plugins/releases) | Plugin ZIP assets on GitHub Releases |

## How It Works

Each plugin lives in `plugins/<plugin-name>/` and must contain a valid `plugin.json`. When a PR is merged to `main`, the publish workflow runs automatically:

- **External plugins** (recommended): the ZIP is fetched from your upstream release URL
- **Standard plugins**: everything in the plugin folder is packaged into a ZIP

The ZIP is then published as a **GitHub Release** on this repository. Manifests and per-plugin READMEs are committed to the [`releases` branch](https://github.com/Dispatcharr/Plugins/tree/releases).

### PR Validation

Every PR runs automated validation that checks:

- Folder name is lowercase-kebab-case
- `plugin.json` is valid and contains required fields
- Version is incremented for existing plugins
- PR author is listed in `author` or `maintainers`
- `.github/` files are not modified by non-maintainers
- Python code is scanned by CodeQL (required check)
- All files are scanned by ClamAV for malware (required check)

PRs where the author has no permission for any modified plugin are automatically closed with instructions.

Results are posted as a comment on the PR.

### Publishing

On merge to `main`, each plugin is:

- Packaged or fetched as a versioned ZIP
- Given MD5 and SHA256 checksums
- Published as a **GitHub Release** (tag: `plugin-name-1.0.0`) with a `-latest` alias release kept up to date
- Listed in `manifest.json` with download URLs pointing to the GitHub Release assets
- Only the 10 most recent versioned releases are kept per plugin

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, including the `plugin.json` spec, validation rules, and what happens after merge.

## Downloading Plugins

Visit the [releases page](https://github.com/Dispatcharr/Plugins/releases) to browse and download plugins, or fetch `manifest.json` programmatically:

```bash
curl https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

## Manifest Structure

The root `manifest.json` uses a `root_url` plus relative paths for ZIP downloads. `manifest_url` is an absolute URL since per-plugin manifests live on the releases branch (not as GitHub Release assets).

```json
{
  "generated_at": "...",
  "signature": "-----BEGIN PGP SIGNATURE-----\n...",
  "manifest": {
    "registry_url": "https://github.com/Dispatcharr/Plugins",
    "registry_name": "Dispatcharr/Plugins",
    "root_url": "https://github.com/Dispatcharr/Plugins/releases/download",
    "plugins": [
      {
        "slug": "my-plugin",
        "name": "My Plugin",
        "manifest_url": "https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/metadata/my-plugin/manifest.json",
        "latest_url": "my-plugin-latest/my-plugin-latest.zip",
        ...
      }
    ]
  }
}
```

To resolve a full ZIP download URL: `root_url + "/" + latest_url`.

The `slug` matches the plugin folder name and can be used to construct other paths (e.g. icon: `plugins/<slug>/logo.png` on the source branch).

## Verifying Manifest Signatures

Each manifest file embeds its GPG signature directly. The `signature` field covers the compact (`jq -c '.manifest'`) form of the `manifest` payload.

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

The same steps apply to any per-plugin manifest - substitute the path to `metadata/<plugin>/manifest.json`.
