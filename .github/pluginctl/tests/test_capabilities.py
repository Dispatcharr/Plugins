from pluginctl import capabilities


def test_future_manifest_versions_use_latest_enforcing_policy():
    assert capabilities.manifest_version_enforces_sandbox(99)
    assert capabilities.manifest_version_parses_capabilities(99)


def test_legacy_and_transition_versions_remain_non_enforcing():
    assert not capabilities.manifest_version_enforces_sandbox(0)
    assert not capabilities.manifest_version_enforces_sandbox(1)
    assert capabilities.manifest_version_enforces_sandbox(2)
    assert capabilities.first_enforcing_manifest_version() == 2


def test_declared_capabilities_preserve_unknown_future_values():
    manifest = {"manifest_version": 99, "capabilities": ["subprocess", "future_capability"]}
    assert capabilities.declared_capabilities(manifest) == {"subprocess", "future_capability"}


def test_legacy_manifest_does_not_parse_capabilities():
    assert capabilities.declared_capabilities({"capabilities": ["subprocess"]}) == set()


def test_async_action_implies_background_tasks_like_dispatcharr():
    assert capabilities.effective_capabilities({
        "manifest_version": 2,
        "actions": [{"id": "refresh", "async": True}],
    }) == {"background_tasks"}


def test_explicit_malformed_manifest_versions_are_invalid():
    assert not capabilities.manifest_version_is_valid({"manifest_version": "two"})
    assert not capabilities.manifest_version_is_valid({"manifest_version": True})
    assert not capabilities.manifest_version_is_valid({"manifest_version": -1})


def test_each_runtime_enforced_static_rule_maps_to_its_capability():
    expected = {
        "background_tasks": "plugin/capability-contract/background-tasks",
        "persistent_service": "plugin/capability-contract/persistent-service",
        "network_listener": "plugin/capability-contract/network-listener",
        "subprocess": "plugin/capability-contract/subprocess",
        "outbound_network": "plugin/capability-contract/outbound-network",
        "celery_dispatch": "plugin/capability-contract/celery-dispatch",
    }
    for capability_id, rule_id in expected.items():
        assert rule_id in capabilities.KNOWN_CAPABILITIES[capability_id]["codeql_rules"]
