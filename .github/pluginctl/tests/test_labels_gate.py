from pluginctl.validate import gate
from pluginctl.validate.labels import decide_labels
from pluginctl import label_catalog


def test_labels_new_plugin():
    d = decide_labels(True, False, "", False, False)
    assert d == {"New Plugin": True, "Plugin Update": False,
                 "Repo Update": False, "Invalid": False}


def test_labels_repo_update_authorized():
    d = decide_labels(False, True, ".github/x", False, False)
    assert d["Repo Update"] is True
    assert d["Invalid"] is False


def test_labels_outside_violation_is_invalid_not_repo_update():
    d = decide_labels(False, True, ".github/x", True, False)
    assert d["Repo Update"] is False
    assert d["Invalid"] is True


def test_labels_close_pr_is_invalid():
    d = decide_labels(False, True, "", False, True)
    assert d["Invalid"] is True


def test_label_catalog_contains_required_automation_labels():
    labels = {label.name: label for label in label_catalog.LABELS}
    assert labels["Plugin Update"].color == "130518"
    assert labels["Auto Merged"].description == "PR was merged automatically after validation"


def test_label_catalog_ensure_reconciles_all_labels(monkeypatch):
    calls = []
    monkeypatch.setattr(label_catalog.gh, "label_create",
                        lambda name, color, description, repo: calls.append((name, color, description, repo)) or 0)
    assert label_catalog.ensure("owner/repo")
    assert len(calls) == len(label_catalog.LABELS)
    assert all(call[-1] == "owner/repo" for call in calls)


def test_label_catalog_ensure_requires_repository(monkeypatch):
    monkeypatch.delenv("GH_REPO", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert not label_catalog.ensure("")


def test_gate_detect_failure():
    r = gate.evaluate("failure", "false", "false", "false", "success",
                      "success", "success", "success", "success", "success", "success")
    assert not r.ok and "detection failed" in r.message


def test_gate_skip_validation_passes():
    r = gate.evaluate("success", "false", "true", "false", "success", "", "", "", "", "", "")
    assert r.ok


def test_gate_skip_validation_fails_for_invalid_title():
    r = gate.evaluate("success", "false", "true", "false", "failure", "", "", "", "", "", "")
    assert not r.ok and "title" in r.message.lower()


def test_gate_title_failure():
    r = gate.evaluate("success", "false", "false", "false", "failure",
                      "success", "success", "success", "success", "success", "success")
    assert not r.ok and "title" in r.message.lower()


def test_gate_all_success():
    r = gate.evaluate("success", "false", "false", "false", "success",
                      "success", "success", "success", "success", "success", "success")
    assert r.ok and "validated successfully" in r.message


def test_gate_test_suite_failure_fails_even_when_skip_validation():
    # A pure repo update (skip_validation=true) must not pass with red tests.
    r = gate.evaluate("success", "false", "true", "false", "", "", "", "", "", "", "",
                      test_result="failure")
    assert not r.ok and "test suite" in r.message.lower()


def test_gate_test_suite_skipped_allows_skip_validation_pass():
    r = gate.evaluate("success", "false", "true", "false", "success", "", "", "", "", "", "",
                      test_result="skipped")
    assert r.ok


def test_gate_test_suite_success_allows_pass():
    r = gate.evaluate("success", "false", "false", "false", "success",
                      "success", "success", "success", "success", "success", "success",
                      test_result="success")
    assert r.ok and "validated successfully" in r.message


def test_gate_ladder_order_outside_violation_before_close():
    # outside_violation takes precedence over close_pr in the ladder
    r = gate.evaluate("success", "true", "false", "true", "success",
                      "success", "success", "success", "success", "success", "success")
    assert not r.ok and "outside the plugins/ directory" in r.message
