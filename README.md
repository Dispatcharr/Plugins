# Dispatcharr Plugin Repository

This repository distributes plugins for Dispatcharr. Develop, test, and release your plugin in its own repository. Submit a pull request here when a version is ready for public use.

> [!NOTE]
> AI tools are used in this repository and may be used in plugins. Contributors are responsible for maintaining their plugins and for the output of any tools used to develop them.

## Find a plugin

| Resource | What it contains |
| --- | --- |
| [Browse published plugin metadata](https://github.com/Dispatcharr/Plugins/tree/releases) | Generated manifests and plugin READMEs |
| [Download a plugin](https://github.com/Dispatcharr/Plugins/releases) | Versioned ZIP files and latest ZIP aliases |
| [Read the root manifest](https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json) | Plugin metadata and download locations |

```bash
curl -O https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

The manifest has a `root_url` and each plugin's relative `latest_url`. Combine them to form a download URL. Each plugin also has an absolute `manifest_url` for its metadata on the `releases` branch.

## Publish a plugin

1. Build and test the plugin in your own repository.
2. Choose how to distribute it:
   - **External plugin**: keep source and release ZIPs in your own repository. This registry stores metadata and retrieves the ZIP for each published version.
   - **Standard plugin**: add the plugin source directly under `plugins/<plugin-slug>/`. The registry packages that directory after merge.
3. Follow the [contribution guide](CONTRIBUTING.md) to create `plugin.json`, prepare the pull request, and understand validation.

Every accepted plugin is published as a GitHub Release in this repository. The registry computes MD5 and SHA256 checksums, updates signed manifests, maintains a `-latest` release, and retains the ten newest versioned releases for each plugin.

## What's allowed

Review the [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a plugin. It defines the repository's contribution boundaries, including requirements for freely usable plugins and clearly disclosed, opt-in phone-home behavior.

## Issues and support

Use this repository's issue tracker for registry matters: validation or publishing workflow problems, submission-process issues, repository tooling, and documentation errors. [Report a repository issue](../../issues/new?template=repo-issue.yml).

For bugs, compatibility problems, support requests, or feature requests for a specific plugin, use that plugin's source repository or its thread in the [Dispatcharr Discord](https://discord.gg/Sp45V5BcxU). To remove a published version from the registry, [submit a Version Removal Request](../../issues/new?template=version-removal-request.yml).

## Pull request validation

GitHub Actions validates plugin submissions before they can merge. Checks cover plugin metadata, versioning, author or maintainer permission, external release details, malware scanning, and static security analysis.

For code changes, CodeQL scans submitted source. ClamAV scans submitted files and external release ZIPs. Capability-contract and sandbox-bypass findings require maintainer review. Read [plugin security](docs/plugin-security.md) for details.

The validation workflow posts a result comment on the pull request. A pull request from an account that is not allowed to modify any affected plugin is closed automatically with instructions.

## License

The registry code, workflows, and documentation are available under the
[GNU Affero General Public License](LICENSE), version 3 or later. Plugins under
`plugins/` remain under their own declared open source licenses.
