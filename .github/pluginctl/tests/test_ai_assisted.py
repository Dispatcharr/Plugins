import subprocess

import pytest

from pluginctl.core import git
from pluginctl.publish import ai_assisted


def _log(author_name="Alice", author_email="alice@example.com", message="Update plugin"):
    return "\x1f".join((author_name, author_email, message)) + "\x1e"


def _stub_log(monkeypatch, output, returncode=0):
    monkeypatch.setattr(
        git, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode, output, ""),
    )


@pytest.mark.parametrize("identity", [
    "Claude Opus 5 (1M context)", "Claude Code", "OpenAI Codex", "Codex", "ChatGPT",
    "GitHub Copilot", "Gemini CLI", "Cursor", "Aider", "Cline", "Roo Code", "Continue",
    "Windsurf", "Codeium", "Devin", "Amp", "Amazon Q", "Tabnine", "JetBrains AI", "Kiro",
    "Augment Code", "Qodo", "CodiumAI", "Sweep AI", "Replit Agent", "Hermes Agent",
])
def test_known_agent_names_are_recognized(identity):
    assert ai_assisted._is_agent_identity(identity, "")


def test_anthropic_coauthor_trailer_is_recognized(monkeypatch):
    _stub_log(monkeypatch, _log(message="Update\n\nCo-authored-by: Claude Opus 5 <noreply@anthropic.com>"))
    assert ai_assisted.has_attribution("main", "demo-plugin")


def test_hermes_trailer_and_nonstandard_key_are_recognized(monkeypatch):
    _stub_log(monkeypatch, _log(message="Generated-by: Hermes Agent <hermes-agent@g1tech.us>"))
    assert ai_assisted.has_attribution("main", "demo-plugin")


def test_agent_primary_author_is_recognized(monkeypatch):
    _stub_log(monkeypatch, _log("Gemini CLI", "bot@example.com"))
    assert ai_assisted.has_attribution("main", "demo-plugin")


def test_case_insensitive_trailer_is_recognized(monkeypatch):
    _stub_log(monkeypatch, _log(message="AI-ASSISTED-BY: github copilot <bot@example.com>"))
    assert ai_assisted.has_attribution("main", "demo-plugin")


def test_human_coauthor_and_agent_prose_are_not_recognized(monkeypatch):
    _stub_log(monkeypatch, _log(message=(
        "This plugin uses an AI agent.\n\nCo-authored-by: Alice <alice@example.com>"
    )))
    assert not ai_assisted.has_attribution("main", "demo-plugin")


def test_no_match_and_git_failure_return_false(monkeypatch):
    _stub_log(monkeypatch, _log())
    assert not ai_assisted.has_attribution("main", "demo-plugin")
    _stub_log(monkeypatch, "", returncode=1)
    assert not ai_assisted.has_attribution("main", "demo-plugin")
