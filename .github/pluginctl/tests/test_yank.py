import json

from pluginctl.core import gh
from pluginctl.publish import yank


def test_needs_rollback_for_latest_existing_release():
    assert yank._needs_rollback(True, True, "2.0.0", "2.0.0")


def test_needs_rollback_skips_non_latest_existing_release():
    assert not yank._needs_rollback(True, False, "2.0.0", "1.0.0")


def test_needs_rollback_resumes_when_source_still_advertises_absent_release():
    assert yank._needs_rollback(False, False, "2.0.0", "2.0.0")


def test_needs_rollback_does_not_repeat_completed_recovery():
    assert not yank._needs_rollback(False, False, "1.0.0", "2.0.0")


def test_absent_release_requires_interrupted_yank_evidence():
    assert not yank._is_recoverable_absent_release(False, False, False)
    assert yank._is_recoverable_absent_release(True, False, False)
    assert yank._is_recoverable_absent_release(False, True, False)
    assert yank._is_recoverable_absent_release(False, False, True)


def test_manifest_has_version(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest": {"versions": [
        {"version": "2.0.0"}, {"version": "1.0.0"},
    ]}}), encoding="utf-8")

    assert yank._manifest_has_version(str(path), "2.0.0")
    assert not yank._manifest_has_version(str(path), "3.0.0")


def test_open_pr_for_branch_returns_matching_pr(monkeypatch):
    monkeypatch.setattr(gh, "api", lambda *args, **kwargs: json.dumps([
        {"html_url": "https://github.com/org/repo/pull/42"},
    ]))

    assert yank._open_pr_for_branch("org/repo", "yank/demo-2.0.0") == "https://github.com/org/repo/pull/42"
