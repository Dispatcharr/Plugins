# pluginctl

The automation CLI behind the plugin-registry workflows. Every piece of logic
that used to live in inline YAML or `.github/scripts/*.sh` now lives here as a
tested Python package, so the workflows are thin wiring and the behavior is
unit-testable.

Standard library only. `git`, `gh`, `gpg`, and `clamscan` come from the CI
runner; there is no build step.

## Layout

```
src/pluginctl/
  cli.py            argparse dispatch (one subcommand per verb)
  core/             shared infra: actions, git, gh, jsonio, models, version
  validate/         PR-time pipeline: detect, title, labels, gate, sarif,
                    langs, clamav, plugin (per-plugin checks), report
  publish/          releases pipeline: manifest, zips, cleanup, readmes, run, yank
  integrations/     webhooks, external_readme, automerge
tests/              pytest suite (pure logic + golden outputs)
fixtures/           sample SARIF and other test inputs
```

## Develop

```bash
cd .github/pluginctl
python -m pytest            # run the suite
```

Run a command locally against a real checkout (cwd must be the repo root so
`plugins/` resolves):

```bash
PYTHONPATH=.github/pluginctl/src python -m pluginctl \
  validate --plugin <slug> --author <you> --base-ref main --out /tmp/frag.md
```

## Command map (old to new)

| Old | New |
|---|---|
| `validate/detect-changes.sh` + inline blacklist | `pluginctl detect` |
| inline `validate-title` job | `pluginctl check-title` |
| inline `label-pr` job | `pluginctl label` |
| inline CodeQL SARIF jq (x3) | `pluginctl sarif` |
| inline CodeQL language detection | `pluginctl detect-langs` |
| inline ClamAV status/table | `pluginctl clamav-report` |
| `validate/validate.sh` | `pluginctl validate` |
| `validate/report.sh` | `pluginctl report` |
| inline gate ladder | `pluginctl gate` |
| `publish/run.sh` (+ chained scripts) | `pluginctl publish` |
| `publish/yank-version.sh` | `pluginctl yank` |
| inline `auto-merge-updates` | `pluginctl automerge` |
| inline `update-external-readme` | `pluginctl external-readme` |
| (new) signed events | `pluginctl webhook` |

## How the workflows wire in

- `.github/actions/gh-app-token` and `.github/actions/trusted-checkout` are
  composite actions (reusable *steps*).
- `.github/workflows/_codeql-scan.yml` and `_clamav-scan.yml` are reusable
  *workflows* (whole jobs), called by `validate-plugin.yml`. They must live in
  `.github/workflows/` per GitHub; the `_` prefix marks them as internal.
- Every `python -m pluginctl` step sets `PYTHONPATH=.github/pluginctl/src`. In
  the CodeQL/ClamAV jobs the package is loaded from a separate base-branch
  checkout (`_trusted/`) so fork code from the PR merge tree is never executed.

## Parity notes for maintainers

- User-facing output (PR comments, manifests, READMEs) must stay byte-identical
  to the old shell. `core/jsonio.py` reproduces `jq -c` exactly, and the
  markdown renderers are ported line for line, guarded by golden tests. PR-comment
  strings are copied verbatim from the old scripts, so match them exactly rather
  than reformatting.
- `publish/readmes.py` intentionally corrects one old bug: deprecated plugins'
  version count now comes from the manifest's `versions[]` instead of the
  removed `zips/` path (which always rendered 0).
