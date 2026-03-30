<!--
  Read CONTRIBUTING.md before submitting: https://github.com/Dispatcharr/Plugins/blob/main/CONTRIBUTING.md

  PR Title format:
    If modifying a single plugin, use your plugin slug (the folder-name of your plugin)
      [plugin-slug]: BRIEF description of changes
      [dispatcharr-exporter]: Bump version to X.X.X

    If modifying more than one plugin, use your github username:
      [author]: BRIEF description of changes
      [sethwv]: Update my plugins to new manifest formatting
-->

## About this submission

<!-- Briefly describe the change: new plugin, update, metadata change, etc. -->

## Pre-submission checklist

<!-- Tick each box that applies. The bot will validate automatically, but catching issues here saves time. -->

**If this is a new plugin:**
- [ ] Plugin folder is named `lowercase-kebab-case`
- [ ] `plugin.json` contains all required fields (`name`, `version`, `description`, `author` or `maintainers`, `license`)
- [ ] My GitHub username is in `author` or `maintainers`
- [ ] `license` is a valid [OSI-approved SPDX identifier](https://spdx.org/licenses/) (e.g. `MIT`, `Apache-2.0`)
- [ ] I have tested the plugin against a running Dispatcharr instance

**If this is an update to an existing plugin:**
- [ ] `version` in `plugin.json` is incremented (unless this is a metadata-only change - see [Versioning](https://github.com/Dispatcharr/Plugins/blob/main/CONTRIBUTING.md#versioning))
- [ ] I am listed in `author` or `maintainers` of the existing plugin
