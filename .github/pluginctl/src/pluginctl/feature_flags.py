"""Hardcoded rollout switches for trusted pluginctl automation."""

# Flip only after the sandbox-bypass query pack has completed its observation period.
# This is deliberately not environment configurable, so PR code cannot enable it.
SANDBOX_BYPASS_DETECTION = False

# Keep legacy root_url manifests until the Python publisher fully replaces the
# shell workflow. This is deliberately not environment configurable.
SPLIT_MANIFEST_BASE_URLS = False
