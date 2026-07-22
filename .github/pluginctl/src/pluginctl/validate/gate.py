"""``pluginctl gate``: port of the ``Plugin PR Check`` evaluation ladder.

This is the single fixed status check referenced by branch protection. The
decision order and messages are preserved exactly; the quarantine-label check is
a separate step that runs first in the workflow and is modeled here too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    ok: bool
    message: str


def evaluate(detect_result: str, close_pr: str, skip_validation: str,
             outside_violation: str, title_result: str,
             codeql_result: str, codeql_status: str,
             clamav_result: str, clamav_status: str,
             validate_result: str, report_result: str,
             test_result: str = "skipped") -> GateResult:
    """Return pass/fail with the exact ::error:: message the Bash ladder emits."""
    if detect_result != "success":
        return GateResult(False, "Plugin detection failed or no plugin changes found.")
    # Tooling test suite gates repo-update PRs. Checked before the skip_validation
    # early-pass so a pure repo update cannot merge with red tests.
    if test_result in ("failure", "cancelled"):
        return GateResult(False, "Tooling test suite failed. See the Test Suite job for details.")
    if skip_validation == "true":
        return GateResult(True, "No plugin changes detected and author has write access - passing.")
    if title_result == "failure":
        return GateResult(False, "PR title does not match the required format. Rename the PR and re-run.")
    if outside_violation == "true":
        return GateResult(False, "PR contains unauthorized changes outside the plugins/ directory.")
    if close_pr == "true":
        return GateResult(False, "PR is unauthorized - no permission to modify these plugins.")
    if codeql_result == "failure" or codeql_status == "failure":
        return GateResult(False, "CodeQL security analysis failed. See the Security tab for details.")
    if clamav_result == "failure" or clamav_status == "failure":
        return GateResult(False, "ClamAV antivirus scan detected threats. See PR comment for details.")
    if validate_result in ("failure", "cancelled"):
        return GateResult(False, "One or more plugin validations failed. See PR comment for details.")
    if report_result != "success":
        return GateResult(False, "Plugin validation failed. See PR comment for details.")
    return GateResult(True, "All plugins validated successfully.")
