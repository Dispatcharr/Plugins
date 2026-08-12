"""CodeQL SARIF parsing: severity bucketing + findings tables.

Replaces the three near-identical ~130-line inline jq programs in
``validate-plugin.yml`` (blocking / medium / low) with one implementation.

Severity model (unchanged): a result's severity is the ``security-severity``
property of its rule (looked up by ``ruleId``), defaulting to 0. Buckets:
  blocking : sev >= 7.0   (HIGH/CRITICAL, fails the PR)
  medium   : 6.0 <= sev < 7.0
  low      : sev < 6.0
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import re
from dataclasses import dataclass

ZWSP = "​"

# jq: \[(?<c>[^\]]+)\][(][0-9]+[)]  ->  .c   (strip markdown [text](123) links)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([0-9]+\)")
_HASH_DIGIT_RE = re.compile(r"#(?=[0-9])")
_WWW_RE = re.compile(r"www\.")
# jq: splits("(?<=[.!?]) ")  ->  split into sentences, dedup, rejoin
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?]) ")


def load_sarif_dir(path: str) -> list[dict]:
    """Load every ``*.sarif`` / ``*.sarif.gz`` under ``path`` (sorted, like the shell glob)."""
    objs: list[dict] = []
    if not os.path.isdir(path):
        return objs
    for pattern in ("*.sarif", "*.sarif.gz"):
        for fn in sorted(glob.glob(os.path.join(path, pattern))):
            if fn.endswith(".gz"):
                with gzip.open(fn, "rt", encoding="utf-8") as fh:
                    objs.append(json.load(fh))
            else:
                with open(fn, encoding="utf-8") as fh:
                    objs.append(json.load(fh))
    return objs


def build_secmap(run: dict) -> dict[str, float]:
    """Map ``ruleId -> security-severity`` from driver rules then extension rules.

    jq's ``from_entries`` keeps the last value for a duplicate key, so extension
    rules override driver rules, reproduced here by inserting driver rules first.
    """
    secmap: dict[str, float] = {}
    driver_rules = (run.get("tool", {}).get("driver", {}) or {}).get("rules") or []
    for rule in driver_rules:
        rid = rule.get("id") or ""
        sev = (rule.get("properties", {}) or {}).get("security-severity", "0")
        secmap[rid] = _to_float(sev)
    for ext in (run.get("tool", {}).get("extensions") or []):
        for rule in (ext.get("rules") or []):
            rid = rule.get("id") or ""
            sev = (rule.get("properties", {}) or {}).get("security-severity", "0")
            secmap[rid] = _to_float(sev)
    return secmap


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rule_id(result: dict) -> str:
    rid = result.get("ruleId")
    if rid is None:
        rid = (result.get("rule") or {}).get("id")
    return "" if rid is None else str(rid)


def severity_of(result: dict, secmap: dict[str, float]) -> float:
    return secmap.get(_rule_id(result), 0.0)


def is_suppressed(result: dict) -> bool:
    """True when CodeQL's own engine recognized and applied a suppression

    (e.g. a correctly-placed inline ``codeql[...]`` comment) - trust that
    signal and never let the result count as blocking/medium/low.
    """
    return len(result.get("suppressions") or []) > 0


@dataclass
class Counts:
    blocking: int = 0
    medium: int = 0
    low: int = 0
    suppressed: int = 0
    total: int = 0

    @property
    def warnings(self) -> int:
        return self.total - self.blocking if self.total > self.blocking else 0


def classify(sarif_objs: list[dict]) -> Counts:
    counts = Counts()
    for obj in sarif_objs:
        for run in obj.get("runs", []):
            secmap = build_secmap(run)
            for result in (run.get("results") or []):
                counts.total += 1
                if is_suppressed(result):
                    counts.suppressed += 1
                    continue
                sev = severity_of(result, secmap)
                if is_blocking(sev):
                    counts.blocking += 1
                elif is_medium(sev):
                    counts.medium += 1
                else:
                    counts.low += 1
    return counts


def process_message(text) -> str:
    """Reproduce the jq message-sanitizing gsub chain, in the same order."""
    msg = "no description" if text is None else str(text)
    msg = msg.replace("\n", " ")
    msg = msg.replace("://", f"{ZWSP}://")
    msg = _WWW_RE.sub(f"www{ZWSP}", msg)
    msg = _HASH_DIGIT_RE.sub(f"#{ZWSP}", msg)
    msg = _MD_LINK_RE.sub(r"\1", msg)
    msg = msg.replace("[", "&#91;").replace("]", "&#93;")
    # Data-flow queries can repeat the same sentence once per source/flow reaching
    # the same sink - collapse repeats while preserving first-seen order.
    sentences = _SENTENCE_SPLIT_RE.split(msg)
    seen: list[str] = []
    for sentence in sentences:
        if sentence not in seen:
            seen.append(sentence)
    return " ".join(seen)


def _location(result: dict) -> tuple[str, str]:
    locs = result.get("locations") or []
    if not locs:
        return "?", "?"
    phys = (locs[0] or {}).get("physicalLocation", {}) or {}
    uri = (phys.get("artifactLocation", {}) or {}).get("uri") or "?"
    start = (phys.get("region", {}) or {}).get("startLine")
    line = "?" if start is None else str(start)
    return uri, line


def findings_table(sarif_objs: list[dict], predicate, repo: str, sha: str,
                   external_prefixes: list[str]) -> str:
    """Render the ``| Rule | Location | Description |`` markdown table.

    ``predicate(sev)`` selects the severity bucket. Locations for files sourced
    from an external ZIP (any of ``external_prefixes``) are rendered as plain
    text since they don't exist in the repo tree.
    """
    lines = ["| Rule | Location | Description |", "|------|----------|-------------|"]
    for obj in sarif_objs:
        for run in obj.get("runs", []):
            secmap = build_secmap(run)
            for result in (run.get("results") or []):
                if is_suppressed(result):
                    continue
                sev = severity_of(result, secmap)
                if not predicate(sev):
                    continue
                rid = _rule_id(result)
                uri, line = _location(result)
                msg = process_message((result.get("message") or {}).get("text"))
                is_external = any(uri.startswith(p) for p in external_prefixes)
                if uri != "?" and line != "?" and not is_external:
                    loc = f"[{uri}:{line}](https://github.com/{repo}/blob/{sha}/{uri}#L{line})"
                else:
                    loc = f"{uri}:{line}"
                lines.append(f"| `{rid}` | {loc} | {msg} |")
    return "\n".join(lines) + "\n"


def suppressed_findings_table(sarif_objs: list[dict], repo: str, sha: str,
                              external_prefixes: list[str]) -> str:
    """Same shape as :func:`findings_table`, but for suppressed results.

    Selection is by ``.suppressions`` rather than a severity bucket.
    """
    lines = ["| Rule | Location | Description |", "|------|----------|-------------|"]
    for obj in sarif_objs:
        for run in obj.get("runs", []):
            for result in (run.get("results") or []):
                if not is_suppressed(result):
                    continue
                rid = _rule_id(result)
                uri, line = _location(result)
                msg = process_message((result.get("message") or {}).get("text"))
                is_external = any(uri.startswith(p) for p in external_prefixes)
                if uri != "?" and line != "?" and not is_external:
                    loc = f"[{uri}:{line}](https://github.com/{repo}/blob/{sha}/{uri}#L{line})"
                else:
                    loc = f"{uri}:{line}"
                lines.append(f"| `{rid}` | {loc} | {msg} |")
    return "\n".join(lines) + "\n"


# Bucket predicates matching JQ_BLOCKING / JQ_MEDIUM / JQ_LOW.
def is_blocking(sev: float) -> bool:
    return sev >= 7.0


def is_medium(sev: float) -> bool:
    return 6.0 <= sev < 7.0


def is_low(sev: float) -> bool:
    return sev < 6.0


def external_prefixes_for(matrix: list[str]) -> list[str]:
    """``plugins/<slug>/`` for every changed plugin whose source_type is external."""
    prefixes: list[str] = []
    for plugin in matrix:
        pjson = os.path.join("plugins", plugin, "plugin.json")
        if not os.path.isfile(pjson):
            continue
        try:
            with open(pjson, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("source_type") or "local") == "external":
            prefixes.append(f"plugins/{plugin}/")
    return prefixes


def compute_status(blocking: int, analyze_failed: bool, languages_found: bool,
                   config_error: bool) -> str:
    """codeql_status ladder: failure > skipped > success (matches the Bash)."""
    if blocking > 0 or analyze_failed:
        return "failure"
    if not languages_found or config_error:
        return "skipped"
    return "success"


def run(results_dir: str, repo: str, sha: str, matrix: list[str],
        analyze_outcome: str, languages_found: bool, languages: str,
        unscanned_langs: str, job_status: str) -> int:
    """Full ``pluginctl sarif`` handler: counts, findings files, status outputs."""
    from ..core import actions

    objs = load_sarif_dir(results_dir)
    counts = classify(objs)
    external_prefixes = external_prefixes_for(matrix)

    actions.log(
        f"Found {counts.blocking} high/critical, {counts.medium} medium, "
        f"{counts.low} low, {counts.suppressed} suppressed, and "
        f"{counts.warnings} other CodeQL result(s)"
    )
    actions.set_output("codeql_errors", str(counts.blocking))
    actions.set_output("codeql_warnings", str(counts.warnings))
    actions.set_output("codeql_mediums", str(counts.medium))
    actions.set_output("codeql_lows", str(counts.low))
    actions.set_output("codeql_suppressed", str(counts.suppressed))

    if counts.blocking > 0 and results_dir:
        _write("codeql-findings.md",
               findings_table(objs, is_blocking, repo, sha, external_prefixes))
    if counts.medium > 0:
        _write("codeql-medium-findings.md",
               findings_table(objs, is_medium, repo, sha, external_prefixes))
    if counts.low > 0:
        _write("codeql-low-findings.md",
               findings_table(objs, is_low, repo, sha, external_prefixes))
    if counts.suppressed > 0:
        _write("codeql-suppressed-findings.md",
               suppressed_findings_table(objs, repo, sha, external_prefixes))

    analyze_failed = languages_found and analyze_outcome not in ("success", "")
    config_error_langs = ""
    if analyze_failed and job_status == "JOB_STATUS_CONFIGURATION_ERROR":
        actions.warning(
            "CodeQL reported a configuration error (no indexable source found) for "
            f"language(s): {languages}. Treating as skipped instead of failing the PR."
        )
        config_error_langs = f"codeql-config-error({languages.replace(',', '+')})"
        unscanned_langs = f"{unscanned_langs},{config_error_langs}" if unscanned_langs else config_error_langs
        analyze_failed = False

    status = compute_status(counts.blocking, analyze_failed, languages_found, bool(config_error_langs))
    actions.set_output("codeql_status", status)
    actions.set_output("codeql_unscanned_langs", unscanned_langs)
    # Always exit 0: the workflow fails the job from a separate step keyed on
    # codeql_status, so the findings-artifact uploads always run first (as in V1).
    return 0


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
