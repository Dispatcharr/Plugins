from pluginctl.validate import langs


def _mk(tmp_path, rel):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")


def test_detect_python_and_order(tmp_path):
    _mk(tmp_path, "plugins/a/main.py")
    _mk(tmp_path, "plugins/a/app.go")
    found, languages, unscanned = langs.detect(str(tmp_path / "plugins"))
    assert found is True
    # Bash order: python before go
    assert languages == "python,go"
    assert unscanned == ""


def test_javascript_prunes_node_modules(tmp_path):
    _mk(tmp_path, "plugins/a/node_modules/pkg/index.js")
    found, languages, _ = langs.detect(str(tmp_path / "plugins"))
    assert "javascript" not in languages
    assert found is False


def test_javascript_detected_outside_pruned(tmp_path):
    _mk(tmp_path, "plugins/a/src/app.ts")
    _, languages, _ = langs.detect(str(tmp_path / "plugins"))
    assert languages == "javascript"


def test_unscanned_types(tmp_path):
    _mk(tmp_path, "plugins/a/run.sh")
    _mk(tmp_path, "plugins/a/lib.rs")
    found, languages, unscanned = langs.detect(str(tmp_path / "plugins"))
    assert found is False
    assert languages == ""
    assert unscanned == "shell,rust"


def test_java_kotlin_group(tmp_path):
    _mk(tmp_path, "plugins/a/Main.kt")
    _, languages, _ = langs.detect(str(tmp_path / "plugins"))
    assert languages == "java-kotlin"
