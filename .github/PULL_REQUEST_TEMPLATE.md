<!--
  Read CONTRIBUTING.md before submitting: https://github.com/Dispatcharr/Plugins/blob/main/CONTRIBUTING.md

  Suggested PR title format: [your-plugin-name]: brief summary of change
  e.g. [dispatcharr-exporter]: add initial release   or   [my-plugin]: bump to 1.2.0
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
