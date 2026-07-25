"""argparse dispatch for ``pluginctl`` / ``python -m pluginctl``.

Each subcommand is a thin wrapper that reads flags (and falls back to the same
environment variables the workflows already set) and delegates to a handler
module. Handlers are imported lazily so a single missing optional dependency or
runtime tool never breaks unrelated commands.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Optional


def _matrix(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _bool(value: Optional[str]) -> bool:
    return str(value).lower() == "true"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _repo(args) -> str:
    """``--repo``, falling back to the repository the workflow runs in."""
    return args.repo or _env("GITHUB_REPOSITORY")


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
def cmd_detect(args) -> int:
    from .validate import detect
    return detect.run(
        pr_author=args.author,
        base_ref=args.base_ref,
        head_ref=args.head_ref or "",
        author_blacklist=_env("AUTHOR_BLACKLIST"),
        plugin_blacklist=_env("PLUGIN_BLACKLIST"),
        repo=_repo(args),
    )


def cmd_check_title(args) -> int:
    from .core import actions
    from .validate import title
    result = title.check_title(args.title, args.author, args.plugin_count, _matrix(args.matrix))
    actions.set_output("title_valid", "true" if result.valid else "false")
    actions.set_output("title_feedback", result.feedback)
    actions.set_output("title_suggestion", result.suggestion)
    if not result.valid:
        actions.error("PR title does not match the required format. See CONTRIBUTING.md for details.")
        return 1
    return 0


def cmd_label(args) -> int:
    from .validate import labels
    return labels.run(
        pr_number=args.pr,
        has_new_plugin=_bool(args.has_new_plugin),
        has_updated_plugin=_bool(args.has_updated_plugin),
        outside_files=args.outside_files or "",
        outside_violation=_bool(args.outside_violation),
        close_pr=_bool(args.close_pr),
    )


def cmd_gate(args) -> int:
    from .core import actions
    from .validate import gate
    result = gate.evaluate(
        detect_result=_env("DETECT_RESULT"),
        close_pr=_env("CLOSE_PR"),
        skip_validation=_env("SKIP_VALIDATION"),
        outside_violation=_env("OUTSIDE_VIOLATION"),
        title_result=_env("TITLE_RESULT"),
        codeql_result=_env("CODEQL_RESULT"),
        codeql_status=_env("CODEQL_STATUS"),
        clamav_result=_env("CLAMAV_RESULT"),
        clamav_status=_env("CLAMAV_STATUS"),
        validate_result=_env("VALIDATE_RESULT"),
        report_result=_env("REPORT_RESULT"),
        test_result=_env("TEST_RESULT", "skipped"),
    )
    if result.ok:
        actions.log(result.message)
        return 0
    actions.error(result.message)
    return 1


def cmd_sarif(args) -> int:
    from .validate import sarif
    return sarif.run(
        results_dir=args.results_dir,
        repo=_repo(args),
        sha=args.sha,
        matrix=_matrix(args.matrix),
        analyze_outcome=args.analyze_outcome,
        languages_found=_bool(args.found),
        languages=args.languages or "",
        unscanned_langs=args.unscanned_langs or "",
        job_status=_env("CODEQL_ACTION_JOB_STATUS"),
    )


def cmd_validate(args) -> int:
    from .validate import plugin as validate
    return validate.run(
        plugin_name=args.plugin,
        pr_author=args.author,
        base_ref=args.base_ref,
        output_file=args.out,
        repo=_repo(args),
    )


def cmd_report(args) -> int:
    from .validate import report
    return report.run(
        pr_number=args.pr,
        pr_author=args.author,
        plugin_count=args.plugin_count,
        close_pr=_bool(args.close_pr),
        fragments_dir=args.fragments_dir,
        repo=_repo(args),
    )


def cmd_detect_langs(args) -> int:
    from .validate import langs
    return langs.run(root=args.root)


def cmd_clamav_report(args) -> int:
    from .validate import clamav
    return clamav.run(output_file=args.output, scan_exit=args.scan_exit,
                      findings_out=args.findings_out)


def cmd_webhook(args) -> int:
    from .integrations import webhooks
    data = json.loads(args.data) if args.data else {}
    webhooks.emit(args.event, data)
    return 0  # emission failures never fail the pipeline


def cmd_publish(args) -> int:
    from .publish import run as publish_run
    return publish_run.run(source_branch=args.source_branch)


def cmd_yank(args) -> int:
    from .publish import yank
    return yank.run()


def cmd_automerge(args) -> int:
    from .integrations import automerge
    return automerge.run(head_sha=args.head_sha or _env("HEAD_SHA"))


def cmd_external_readme(args) -> int:
    from .integrations import external_readme
    return external_readme.run()


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pluginctl", description="Dispatcharr plugin registry automation")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", help="Detect changed plugins and build the matrix")
    p.add_argument("--author", required=True)
    p.add_argument("--base-ref", required=True)
    p.add_argument("--head-ref", default="")
    p.add_argument("--repo", default="")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("check-title", help="Validate the PR title format")
    p.add_argument("--title", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--plugin-count", type=int, default=0)
    p.add_argument("--matrix", default="[]")
    p.set_defaults(func=cmd_check_title)

    p = sub.add_parser("label", help="Reconcile PR classification labels")
    p.add_argument("--pr", required=True)
    p.add_argument("--has-new-plugin", default="false")
    p.add_argument("--has-updated-plugin", default="false")
    p.add_argument("--outside-files", default="")
    p.add_argument("--outside-violation", default="false")
    p.add_argument("--close-pr", default="false")
    p.set_defaults(func=cmd_label)

    p = sub.add_parser("gate", help="Evaluate the Plugin PR Check gate (env-driven)")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("sarif", help="Parse CodeQL SARIF: counts, tables, status")
    p.add_argument("--results-dir", default="sarif-results")
    p.add_argument("--repo", default="")
    p.add_argument("--sha", default="")
    p.add_argument("--matrix", default="[]")
    p.add_argument("--analyze-outcome", default="")
    p.add_argument("--found", default="false")
    p.add_argument("--languages", default="")
    p.add_argument("--unscanned-langs", default="")
    p.set_defaults(func=cmd_sarif)

    p = sub.add_parser("validate", help="Validate one plugin -> markdown fragment")
    p.add_argument("--plugin", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--base-ref", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--repo", default="")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("report", help="Aggregate fragments, post PR comment")
    p.add_argument("--pr", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--plugin-count", required=True)
    p.add_argument("--close-pr", default="false")
    p.add_argument("--fragments-dir", default=".")
    p.add_argument("--repo", default="")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("detect-langs", help="Detect CodeQL languages in changed plugins")
    p.add_argument("--root", default="plugins")
    p.set_defaults(func=cmd_detect_langs)

    p = sub.add_parser("clamav-report", help="Parse clamscan output: status + findings table")
    p.add_argument("--output", default="clamav-output.txt")
    p.add_argument("--scan-exit", type=int, default=0)
    p.add_argument("--findings-out", default="clamav-findings.md")
    p.set_defaults(func=cmd_clamav_report)

    p = sub.add_parser("webhook", help="Emit a signed webhook event")
    p.add_argument("--event", required=True)
    p.add_argument("--data", default="{}")
    p.set_defaults(func=cmd_webhook)

    p = sub.add_parser("publish", help="Publish plugins to the releases branch")
    p.add_argument("source_branch")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("yank", help="Yank a plugin version (env-driven)")
    p.set_defaults(func=cmd_yank)

    p = sub.add_parser("automerge", help="Auto-merge a pure plugin-update PR")
    p.add_argument("--head-sha", default="")
    p.set_defaults(func=cmd_automerge)

    p = sub.add_parser("external-readme", help="Open/update the external README PR (env-driven)")
    p.set_defaults(func=cmd_external_readme)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
