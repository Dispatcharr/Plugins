# Verify manifest signatures

Every manifest embeds a GPG signature for its compact `manifest` payload. The Dispatcharr public key is bundled with the application and is also available at `.github/scripts/keys/dispatcharr-plugins.pub` on the default branch.

```bash
gpg --import dispatcharr-plugins.pub
curl -sO https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
jq -c '.manifest' manifest.json | gpg --verify <(jq -r '.signature' manifest.json) -
```

The same process works for a per-plugin manifest from `metadata/<plugin-slug>/manifest.json` on the `releases` branch.
