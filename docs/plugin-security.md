# Plugin Security Checks

Plugin source is checked before merge in two layers. This repository runs static
analysis while the Dispatcharr application enforces runtime plugin sandboxing.
Neither layer is a proof that a plugin is safe, but together they give reviewers
useful signals before distribution.

## Sandbox-bypass queries

The Python CodeQL pack detects shapes associated with attempts to bypass a
Python-level plugin sandbox:

| Rule | Detection |
|---|---|
| `sys-modules-tamper` | Replacement of sensitive `sys.modules` entries |
| `ctypes-usage` | Native-code access through `ctypes` |
| `builtins-mutation` | Mutation of `__builtins__` |
| `subclass-gadget-exact` | Subclass enumeration escape primitives |
| `subclass-gadget-broad` | Broad introspection access to subclasses, globals, or MRO |
| `frame-globals-write` | Writes through frame globals or locals |
| `obfuscated-dynamic-resolution` | Dynamic code evaluation |

The feature is shipped disabled while its query behavior is reviewed. Its single
hardcoded switch is `pluginctl.feature_flags.SANDBOX_BYPASS_DETECTION`. When a
maintainer enables it, all of these rules remain informational. They do not
create a high or critical CodeQL result and do not fail the required validation
check.

An enabled finding applies the `Sandbox Bypass Detected` label and blocks only
automatic merging. A maintainer must review the finding before manually merging
the PR. Removing the detected code removes the label on the next validation run.

## Suppressions

Use an inline `codeql[rule-id]` suppression only for a justified exception. A
suppressed sandbox result still applies `Sandbox Bypass Detected`, and the
existing `CodeQL Suppression Used` label also blocks automatic merge. Both labels
require maintainer review.
