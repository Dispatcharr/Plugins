from pluginctl.core import release_links as links


def external(version, source_url, repo_url="https://github.com/acme/widget"):
    return {"source_type": "external", "version": version,
            "source_url": source_url, "repo_url": repo_url}


def test_github_download_source_requires_release_download_url():
    assert links.github_download_source(
        "https://github.com/acme/widget/releases/download/release-1/widget.zip"
    ) == ("acme/widget", "release-1")
    assert links.github_download_source("https://github.com/acme/widget/releases/tag/release-1") is None
    assert links.github_download_source("https://downloads.example/widget.zip") is None


def test_external_links_use_exact_tags_from_source_urls():
    previous = external("1.0.0", "https://github.com/acme/widget/releases/download/release-{version}/widget.zip")
    current = external("1.1.0-rc.1", "https://github.com/acme/widget/releases/download/release-{version}/widget.zip")
    result = links.external_links(current, previous)
    assert result.current_label == "release-1.1.0-rc.1"
    assert result.current_url.endswith("/releases/tag/release-1.1.0-rc.1")
    assert result.compare_label == "release-1.0.0...release-1.1.0-rc.1"
    assert result.compare_url.endswith("/compare/release-1.0.0...release-1.1.0-rc.1")


def test_external_links_omit_compare_for_same_tag_or_changed_upstream():
    current = external("1.0.0", "https://github.com/acme/widget/releases/download/v{version}/widget.zip")
    same_tag = external("1.0.0", "https://github.com/acme/widget/releases/download/v{version}/other.zip")
    other_repo = external("0.9.0", "https://github.com/other/widget/releases/download/v{version}/widget.zip")
    assert not links.external_links(current, same_tag).compare_url
    assert not links.external_links(current, other_repo).compare_url


def test_external_links_omit_compare_for_same_version_replacement():
    current = external("1.0.0-pre.1", "https://github.com/acme/widget/releases/download/new-{version}/widget.zip")
    previous = external("1.0.0-pre.1", "https://github.com/acme/widget/releases/download/old-{version}/widget.zip")
    assert not links.external_links(current, previous).compare_url


def test_external_links_omit_non_github_sources():
    current = external("1.0.0", "https://downloads.example/widget-{version}.zip")
    assert links.external_links(current).current_url == ""


def test_standard_links_compare_source_commits():
    result = links.standard_links("org/registry", "b" * 40, "a" * 40)
    assert result.current_label == "bbbbbbb"
    assert result.current_url.endswith("/commit/" + "b" * 40)
    assert result.compare_label == "aaaaaaa...bbbbbbb"
    assert result.compare_url.endswith("/compare/" + "a" * 40 + "..." + "b" * 40)


def test_standard_links_first_release_has_no_comparison():
    assert not links.standard_links("org/registry", "b" * 40).compare_url
