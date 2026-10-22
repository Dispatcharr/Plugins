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


def cmd_discord_webhook(args) -> int:
    from .integrations import webhooks
    repository = _repo(args)
    events = sorted(webhooks.SUPPORTED_DISCORD_EVENTS) if args.event == "all" else [args.event]
    if args.data and args.event == "all":
        raise ValueError("--data cannot be combined with --event all")
    for event in events:
        data = json.loads(args.data) if args.data else _discord_fixture(event)
        if args.random:
            repository = "Dispatcharr/Plugins"
            data = _random_discord_fixture(event, repository)
        payload = webhooks.discord_payload(event, data, repository)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if not args.send:
            continue
        temporary_attachment = ""
        temporary_directory = ""
        if data.get("attachment_url") and not data.get("attachment_path"):
            import tempfile
            import urllib.request
            temporary_directory = tempfile.mkdtemp(prefix="pluginctl-discord-")
            temporary_attachment = os.path.join(temporary_directory, data["attachment_filename"])
            with urllib.request.urlopen(data["attachment_url"], timeout=30) as response:
                with open(temporary_attachment, "wb") as fh:
                    fh.write(response.read())
            data["attachment_path"] = temporary_attachment
        try:
            webhooks.emit_discord(event, data, repository=repository, url=args.webhook_url or None)
        finally:
            if temporary_attachment:
                os.unlink(temporary_attachment)
            if temporary_directory:
                os.rmdir(temporary_directory)
    return 0


def _discord_fixture(event: str) -> dict:
    fixtures = {
        "plugin.published": {"plugin": "example-plugin", "version": "1.2.3", "release_url": "https://github.com/example/plugins/releases"},
        "pr.auto_merged": {"pr": "42", "author": "octocat", "plugins": ["example-plugin"]},
        "pr.review_required": {"pr": "42", "author": "octocat", "plugins": ["example-plugin"], "reason": "Manual review is required."},
    }
    return fixtures[event]


def _random_discord_fixture(event: str, repo: str) -> dict:
    """Use a real, logo-bearing Dispatcharr/Plugins candidate for simulation."""
    import base64
    import random
    from .core import gh

    def logo_url(plugin: str, ref: str) -> str:
        path = logos.get(plugin)
        return f"https://raw.githubusercontent.com/{repo}/main/{path}" if path else ""

    tree = gh.loads(gh.api(f"repos/{repo}/git/trees/main?recursive=1")) or {}
    logos = {}
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if path.startswith("plugins/") and path.rsplit("/", 1)[-1] in {
            "logo.png", "logo.svg", "logo.jpg", "logo.webp",
        }:
            logos.setdefault(path.split("/")[1], path)

    if event == "plugin.published":
        plugins = sorted(logos)
        if not plugins:
            raise ValueError("No logo-bearing plugins found in Dispatcharr/Plugins.")
        from .core import version as version_util
        published = [(candidate, version_util.versioned_tags(gh.release_list_tags(repo), candidate))
                     for candidate in plugins]
        published = [(candidate, tags) for candidate, tags in published if tags]
        if not published:
            raise ValueError("No published releases found for logo-bearing plugins.")
        plugin, release_tags = random.choice(published)
        manifest = gh.loads(gh.api(f"repos/{repo}/contents/plugins/{plugin}/plugin.json?ref=main")) or {}
        raw = json.loads(base64.b64decode(manifest["content"]).decode("utf-8"))
        tag = release_tags[0]
        version = tag[len(plugin) + 1:]
        asset_url = f"https://github.com/{repo}/releases/download/{tag}/{tag}.zip"
        links = []
        upstream = str(raw.get("repo_url") or "").rstrip("/")
        external_upstream = raw.get("source_type") == "external" and upstream.startswith("https://github.com/")
        if not external_upstream:
            upstream = f"https://github.com/{repo}"
        source_tag = f"v{version}" if external_upstream else tag
        if external_upstream:
            links.append(f"[v{version}]({upstream}/releases/tag/{source_tag})")
        previous = [entry for entry in release_tags if entry != tag]
        if previous:
            previous_tag = previous[0]
            previous_version = previous_tag[len(plugin) + 1:]
            if external_upstream:
                links.append(f"[v{previous_version}...v{version}]({upstream}/compare/v{previous_version}...v{version})")
        release_manifest = gh.loads(gh.api(
            f"repos/{repo}/contents/metadata/{plugin}/manifest.json?ref=releases"
        )) or {}
        try:
            release_data = json.loads(base64.b64decode(release_manifest["content"]).decode("utf-8"))
            versions = (release_data.get("manifest") or {}).get("versions") or []
            source_sha = next((str(entry.get("commit_sha") or "") for entry in versions
                               if str(entry.get("version")) == version), "")
            if not external_upstream and source_sha:
                links.append(f"[{source_sha[:7]}]({upstream}/commit/{source_sha})")
        except (KeyError, ValueError, TypeError):
            source_sha = ""
        pr_number, pr_url = gh.commit_pull_number(repo, source_sha) if source_sha else (None, None)
        if pr_number and pr_url:
            links.append(f"[#{pr_number}]({pr_url})")
        return {"plugin": plugin, "version": version, "description": str(raw.get("description") or ""),
                "author": str(raw.get("author") or "unknown"),
                "logo_url": logo_url(plugin, "main"),
                "release_url": f"https://github.com/{repo}/releases/tag/{tag}",
                "metadata": "-# " + " · ".join(links),
                "attachment_filename": f"{tag}.zip", "attachment_url": asset_url}

    fields = "number,author,url,headRefOid,mergedAt,labels"
    state = "closed" if event == "pr.auto_merged" else "open"
    prs = gh.loads(gh.pr_list(repo, state, fields, limit=100)) or []
    def merged_plugin_prs(candidates: list[dict]) -> list[dict]:
        return [pr for pr in candidates if pr.get("mergedAt") and any(
            label.get("name") in {"New Plugin", "Plugin Update"}
            for label in (pr.get("labels") or [])
        )]
    if event == "pr.auto_merged":
        prs = merged_plugin_prs(prs)
    elif event == "pr.review_required":
        # Prefer a live review candidate. If none has a logo, include real merged
        # plugin PRs so --random remains useful for Components V2 layout testing.
        prs += merged_plugin_prs(gh.loads(gh.pr_list(repo, "closed", fields, limit=100)) or [])
    random.shuffle(prs)
    candidates = []
    for pr in prs[:25]:
        paths = gh.pr_files(str(pr["number"]), repo) or []
        plugins = sorted({path.split("/")[1] for path in paths if path.startswith("plugins/")
                          and path.count("/") >= 2 and path.split("/")[1] in logos})
        for plugin in plugins:
            logo = logo_url(plugin, pr.get("headRefOid", ""))
            if logo:
                candidates.append((pr, plugin, logo))
                break
    if not candidates:
        raise ValueError(f"No {state} logo-bearing plugin PRs found in Dispatcharr/Plugins.")
    pr, plugin, logo = random.choice(candidates)
    raw_plugin = gh.loads(gh.api(
        f"repos/{repo}/contents/plugins/{plugin}/plugin.json?ref={pr.get('headRefOid', '')}"
    )) or {}
    try:
        plugin_data = json.loads(base64.b64decode(raw_plugin["content"]).decode("utf-8"))
    except (KeyError, ValueError, TypeError):
        plugin_data = {}
    upstream = str(plugin_data.get("repo_url") or "").rstrip("/")
    current_version = str(plugin_data.get("version") or "")
    links = []
    if current_version:
        external_upstream = plugin_data.get("source_type") == "external" and upstream.startswith("https://github.com/")
        if not external_upstream:
            upstream = f"https://github.com/{repo}"
        current_tag = f"v{current_version}" if external_upstream else f"{plugin}-{current_version}"
        if external_upstream:
            links.append(f"[v{current_version}]({upstream}/releases/tag/{current_tag})")
        pr_detail = gh.loads(gh.api(f"repos/{repo}/pulls/{pr['number']}")) or {}
        base_sha = ((pr_detail.get("base") or {}).get("sha") or "")
        base_plugin = gh.loads(gh.api(
            f"repos/{repo}/contents/plugins/{plugin}/plugin.json?ref={base_sha}"
        )) or {}
        try:
            base_data = json.loads(base64.b64decode(base_plugin["content"]).decode("utf-8"))
            previous_version = str(base_data.get("version") or "")
        except (KeyError, ValueError, TypeError):
            previous_version = ""
        if previous_version and previous_version != current_version:
            previous_tag = f"v{previous_version}" if external_upstream else f"{plugin}-{previous_version}"
            links.append(f"[v{previous_version}...v{current_version}]({upstream}/compare/{previous_tag}...{current_tag})")
    return {"pr": str(pr["number"]), "author": str(plugin_data.get("author") or "unknown"),
            "pr_url": pr.get("url", ""), "plugins": [plugin], "plugin_name": plugin_data.get("name") or plugin,
            "description": str(plugin_data.get("description") or ""),
            "source_links": "-# " + " · ".join(links), "logo_url": logo}


def cmd_publish(args) -> int:
    from .publish import run as publish_run
    return publish_run.run(source_branch=args.source_branch)


def cmd_yank(args) -> int:
    from .publish import yank
    return yank.run()


def cmd_unlist(args) -> int:
    from .publish import unlist
    return unlist.run()


def cmd_automerge(args) -> int:
    from .integrations import automerge
    return automerge.run(head_sha=args.head_sha or _env("HEAD_SHA"), disabled_reason=args.disabled_reason)


def cmd_ensure_labels(args) -> int:
    from . import label_catalog
    return 0 if label_catalog.ensure(_repo(args)) else 1


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

    p = sub.add_parser("discord-webhook", help="Preview or send a Discord Components V2 event")
    p.add_argument("--event", required=True, choices=["all", "plugin.published", "pr.auto_merged", "pr.review_required"])
    p.add_argument("--data", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--random", action="store_true")
    p.add_argument("--send", action="store_true")
    p.add_argument("--webhook-url", default="")
    p.set_defaults(func=cmd_discord_webhook)

    p = sub.add_parser("publish", help="Publish plugins to the releases branch")
    p.add_argument("source_branch")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("yank", help="Yank a plugin version (env-driven)")
    p.set_defaults(func=cmd_yank)

    p = sub.add_parser("unlist", help="Open a PR to unlist a plugin (env-driven)")
    p.set_defaults(func=cmd_unlist)

    p = sub.add_parser("automerge", help="Auto-merge a pure plugin-update PR")
    p.add_argument("--head-sha", default="")
    p.add_argument("--disabled-reason", default="")
    p.set_defaults(func=cmd_automerge)

    p = sub.add_parser("ensure-labels", help="Create or update labels required by pluginctl")
    p.add_argument("--repo", default="")
    p.set_defaults(func=cmd_ensure_labels)

    p = sub.add_parser("external-readme", help="Open/update the external README PR (env-driven)")
    p.set_defaults(func=cmd_external_readme)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
