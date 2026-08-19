from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.tool_center.contracts import ToolContext, ToolResult
from app.tool_registry import compat
from app.tool_registry.compat import (
    CAPABILITY_TO_LEGACY_NAME,
    LEGACY_NAME_TO_CAPABILITY,
    discover_tools,
    execute_tool,
    get_tool_gateway,
    get_tool_registry,
    reset_runtime_for_tests,
)
from app.tool_registry.seed import seed_builtin_tools
from app.tools.register import register_all_tools

from tests.tool_registry._helpers import make_sqlite_session_factory

INTERNAL = ToolContext(caller_type="internal")
TENANT_INTERNAL = ToolContext(
    caller_type="internal",
    tenant_id="tenant-a",
    role="operator",
    user_id="operator-1",
)


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.result = ToolResult(success=True, data={"ok": True})

    def execute(self, capability, arguments, context, confirmation_token=None, stable_only=False):
        self.calls.append((capability, arguments, context, confirmation_token, stable_only))
        return self.result


class FakeRegistry:
    def __init__(self, descriptors=None) -> None:
        self.descriptors = descriptors or []
        self.discover_calls: list[ToolContext] = []

    def discover(self, context, capability=None):
        self.discover_calls.append(context)
        return self.descriptors


def test_legacy_mode_uses_current_registry(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")
    register_all_tools()

    result = execute_tool("kpi_query", {"department": "安全环保部"}, INTERNAL)

    assert result.success is True
    assert result.metadata["source"] == "mock_ioc_api"


def test_legacy_mode_accepts_capability_names(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")
    register_all_tools()

    result = execute_tool("query.kpi", {"department": "安全环保部"}, INTERNAL)

    assert result.success is True


def test_database_mode_translates_legacy_name(monkeypatch) -> None:
    fake_gateway = FakeGateway()
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    monkeypatch.setattr(compat, "get_tool_gateway", lambda: fake_gateway)

    result = execute_tool(
        "kpi_query",
        {"a": 1},
        INTERNAL,
        confirmation_token="tok-1",
        stable_only=True,
    )

    assert result is fake_gateway.result
    assert fake_gateway.calls == [
        ("query.kpi", {"a": 1}, INTERNAL, "tok-1", True),
    ]


def test_database_mode_passes_unknown_capability_through(monkeypatch) -> None:
    fake_gateway = FakeGateway()
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    monkeypatch.setattr(compat, "get_tool_gateway", lambda: fake_gateway)

    execute_tool("custom.capability", {}, INTERNAL)

    assert fake_gateway.calls[0][0] == "custom.capability"


def test_legacy_to_capability_mapping_is_complete() -> None:
    assert set(LEGACY_NAME_TO_CAPABILITY) == {
        "kpi_query",
        "alarm_query",
        "risk_query",
        "work_order_query",
        "ioc_summary_analysis",
        "work_order_draft",
    }
    for name, capability in LEGACY_NAME_TO_CAPABILITY.items():
        assert CAPABILITY_TO_LEGACY_NAME[capability] == name


def test_discover_tools_legacy_mode(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tool_registry_mode", "legacy")
    register_all_tools()

    descriptors = discover_tools(INTERNAL)

    by_key = {descriptor.tool_key: descriptor for descriptor in descriptors}
    assert by_key["kpi_query"].capability == "query.kpi"
    assert by_key["work_order_draft"].tool_type.value == "action"
    assert by_key["work_order_draft"].action_phase.value == "prepare"
    assert by_key["ioc_summary_analysis"].tool_type.value == "analysis"
    assert by_key["kpi_query"].version == "legacy"


def test_discover_tools_database_mode(monkeypatch) -> None:
    fake_registry = FakeRegistry(descriptors=[])
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    monkeypatch.setattr(compat, "get_tool_registry", lambda: fake_registry)

    assert discover_tools(TENANT_INTERNAL) == []
    assert fake_registry.discover_calls == [TENANT_INTERNAL]


def test_lazy_runtime_builds_registry_from_session_factory(monkeypatch) -> None:
    session_factory = make_sqlite_session_factory()
    with session_factory() as session:
        seed_builtin_tools(session)
        session.commit()
    monkeypatch.setattr(compat, "get_session_local", lambda: session_factory)
    reset_runtime_for_tests()
    try:
        registry = get_tool_registry()

        resolved = registry.resolve("query.kpi", INTERNAL)

        assert resolved.version == "1.0.0"
        assert resolved.implementation_ref == "builtin.kpi_query"
    finally:
        reset_runtime_for_tests()


def test_lazy_gateway_executes_governed_call(monkeypatch) -> None:
    session_factory = make_sqlite_session_factory()
    with session_factory() as session:
        seed_builtin_tools(session)
        session.commit()
    register_all_tools()
    monkeypatch.setattr(compat, "get_session_local", lambda: session_factory)
    monkeypatch.setattr(settings, "tool_registry_mode", "database")
    reset_runtime_for_tests()
    try:
        result = execute_tool("kpi_query", {"department": "安全环保部"}, INTERNAL)

        assert result.success is True
        assert result.metadata["tool_key"] == "kpi_query"
        assert result.metadata["tool_version"] == "1.0.0"
        assert result.metadata["implementation_ref"] == "builtin.kpi_query"
    finally:
        reset_runtime_for_tests()
        monkeypatch.setattr(settings, "tool_registry_mode", "legacy")


def test_reset_runtime_for_tests_clears_singletons(monkeypatch) -> None:
    session_factory = make_sqlite_session_factory()
    with session_factory() as session:
        seed_builtin_tools(session)
        session.commit()
    monkeypatch.setattr(compat, "get_session_local", lambda: session_factory)
    reset_runtime_for_tests()
    try:
        first = get_tool_registry()
        second = get_tool_registry()
        assert first is second

        reset_runtime_for_tests()
        third = get_tool_registry()
        assert third is not first
    finally:
        reset_runtime_for_tests()
