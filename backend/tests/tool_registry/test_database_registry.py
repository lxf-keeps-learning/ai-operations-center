from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.tool_center.contracts import ToolContext
from app.tool_center.exceptions import (
    CapabilityUnavailableError,
    RegistryUnavailableError,
    ToolForbiddenError,
)
from app.tool_registry.contracts import (
    ActionPhase,
    GovernanceDecision,
    ToolDefinitionRecord,
    ToolPolicyRecord,
    ToolType,
    ToolVersionRecord,
    VersionStatus,
)
from app.tool_registry.registry import DatabaseToolRegistry

from tests.tool_registry._helpers import (
    FakeClock,
    SnapshotLoader,
    make_definition,
    make_policy,
    make_version,
)

KPI = make_definition(1, "kpi_query", "query.kpi", "KPI Query", "Returns KPI data")
KPI_STABLE = make_version(11, 1, version="1.0.0", implementation_ref="builtin.kpi_query")
KPI_GRAY = make_version(
    12,
    1,
    version="1.1.0",
    implementation_ref="builtin.kpi_query.v110",
    is_stable=False,
)

DRAFT_TOOL = make_definition(2, "draft_tool", "query.draft")
DRAFT_VERSION = make_version(
    21,
    2,
    implementation_ref="builtin.draft_tool",
    status=VersionStatus.DRAFT,
)

DISABLED_TOOL = make_definition(3, "disabled_tool", "query.disabled", enabled=False)

DRAFT_ACTION = make_definition(
    4,
    "work_order_draft",
    "action.work_order.draft",
    tool_type=ToolType.ACTION,
    action_phase=ActionPhase.PREPARE,
)
DRAFT_ACTION_VERSION = make_version(
    41,
    4,
    version="1.0.0",
    implementation_ref="builtin.work_order_draft",
)

TOOL_DEFAULT_POLICY = make_policy(1, 1)
GRAY_POLICY = make_policy(2, 1, version_id=12, gray_percentage=100)
ACTION_POLICY = make_policy(4, 4)

INTERNAL = ToolContext(caller_type="internal", tenant_id="tenant-a", role="operator")
EXTERNAL = ToolContext(caller_type="external", tenant_id="tenant-a", role="operator")
NO_TENANT_INTERNAL = ToolContext(caller_type="internal")


def _build_registry(
    definitions: Sequence[ToolDefinitionRecord],
    versions: Sequence[ToolVersionRecord],
    policies: Sequence[ToolPolicyRecord],
    *,
    clock: FakeClock | None = None,
    stale_query_ttl_seconds: int = 86400,
) -> tuple[DatabaseToolRegistry, SnapshotLoader]:
    clock = clock or FakeClock()
    loader = SnapshotLoader(definitions, versions, policies, clock=clock)
    registry = DatabaseToolRegistry(
        loader,
        cache_ttl_seconds=30,
        stale_query_ttl_seconds=stale_query_ttl_seconds,
        clock=clock,
    )
    return registry, loader


def test_discover_returns_enabled_published_descriptors() -> None:
    registry, _loader = _build_registry(
        (KPI, DRAFT_TOOL, DISABLED_TOOL, DRAFT_ACTION),
        (KPI_STABLE, DRAFT_VERSION, DRAFT_ACTION_VERSION),
        (TOOL_DEFAULT_POLICY, ACTION_POLICY),
    )

    descriptors = registry.discover(INTERNAL)

    assert sorted(descriptor.tool_key for descriptor in descriptors) == [
        "kpi_query",
        "work_order_draft",
    ]
    kpi = next(descriptor for descriptor in descriptors if descriptor.tool_key == "kpi_query")
    assert kpi.capability == "query.kpi"
    assert kpi.version == "1.0.0"
    assert kpi.version_id == 11
    assert kpi.selected_stable is True
    assert kpi.rate_limit_per_minute == 60
    assert kpi.input_schema == {"type": "object"}
    assert kpi.tool_type is ToolType.QUERY


def test_discover_filters_by_capability() -> None:
    registry, _loader = _build_registry(
        (KPI, DRAFT_ACTION),
        (KPI_STABLE, DRAFT_ACTION_VERSION),
        (TOOL_DEFAULT_POLICY, ACTION_POLICY),
    )

    descriptors = registry.discover(INTERNAL, capability="action.work_order.draft")

    assert [descriptor.tool_key for descriptor in descriptors] == ["work_order_draft"]


def test_discover_excludes_tools_invisible_to_caller() -> None:
    registry, _loader = _build_registry((KPI,), (KPI_STABLE,), ())

    assert registry.discover(EXTERNAL) == []
    assert [descriptor.tool_key for descriptor in registry.discover(INTERNAL)] == ["kpi_query"]


def test_resolve_returns_stable_by_default() -> None:
    registry, _loader = _build_registry((KPI,), (KPI_STABLE,), (TOOL_DEFAULT_POLICY,))

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.version_id == 11
    assert resolved.version == "1.0.0"
    assert resolved.selected_stable is True
    assert resolved.gray_bucket is None
    assert resolved.policy_id == 1
    assert resolved.rate_limit_per_minute == 60
    assert resolved.implementation_ref == "builtin.kpi_query"
    assert resolved.tool_key == "kpi_query"
    assert resolved.capability == "query.kpi"


def test_resolve_selects_gray_for_hit_bucket() -> None:
    registry, _loader = _build_registry(
        (KPI,),
        (KPI_STABLE, KPI_GRAY),
        (TOOL_DEFAULT_POLICY, GRAY_POLICY),
    )

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.version_id == 12
    assert resolved.version == "1.1.0"
    assert resolved.selected_stable is False
    assert resolved.gray_bucket is not None
    assert resolved.policy_id == 2


def test_resolve_missing_tenant_always_selects_stable() -> None:
    registry, _loader = _build_registry(
        (KPI,),
        (KPI_STABLE, KPI_GRAY),
        (TOOL_DEFAULT_POLICY, GRAY_POLICY),
    )

    resolved = registry.resolve("query.kpi", NO_TENANT_INTERNAL)

    assert resolved.version_id == 11
    assert resolved.selected_stable is True


def test_resolve_stable_only_forces_stable() -> None:
    registry, _loader = _build_registry(
        (KPI,),
        (KPI_STABLE, KPI_GRAY),
        (TOOL_DEFAULT_POLICY, GRAY_POLICY),
    )

    resolved = registry.resolve("query.kpi", INTERNAL, stable_only=True)

    assert resolved.version_id == 11
    assert resolved.selected_stable is True


def test_resolve_gray_denied_falls_back_to_stable() -> None:
    gray_deny = make_policy(
        3,
        1,
        version_id=12,
        decision=GovernanceDecision.DENY,
        gray_percentage=100,
    )
    registry, _loader = _build_registry(
        (KPI,),
        (KPI_STABLE, KPI_GRAY),
        (TOOL_DEFAULT_POLICY, gray_deny),
    )

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.version_id == 11
    assert resolved.selected_stable is True
    assert resolved.gray_bucket is not None


def test_resolve_denied_policy_raises_forbidden() -> None:
    deny = make_policy(2, 1, decision=GovernanceDecision.DENY)
    registry, _loader = _build_registry((KPI,), (KPI_STABLE,), (deny,))

    with pytest.raises(ToolForbiddenError):
        registry.resolve("query.kpi", INTERNAL)


def test_resolve_version_policy_overrides_tool_policy() -> None:
    version_policy = make_policy(
        3,
        1,
        version_id=11,
        tenant_id="tenant-a",
        role="operator",
        rate_limit_per_minute=120,
    )
    registry, _loader = _build_registry(
        (KPI,),
        (KPI_STABLE,),
        (TOOL_DEFAULT_POLICY, version_policy),
    )

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.policy_id == 3
    assert resolved.rate_limit_per_minute == 120


def test_resolve_without_matching_policy_allows_internal_only() -> None:
    registry, _loader = _build_registry((KPI,), (KPI_STABLE,), ())

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.policy_id is None
    assert resolved.rate_limit_per_minute == 60

    with pytest.raises(ToolForbiddenError):
        registry.resolve("query.kpi", EXTERNAL)


def test_resolve_unknown_capability_raises_unavailable() -> None:
    registry, _loader = _build_registry((KPI,), (KPI_STABLE,), (TOOL_DEFAULT_POLICY,))

    with pytest.raises(CapabilityUnavailableError):
        registry.resolve("query.unknown", INTERNAL)


def test_resolve_disabled_tool_raises_unavailable() -> None:
    disabled_version = make_version(
        31,
        3,
        implementation_ref="builtin.disabled_tool",
    )
    registry, _loader = _build_registry(
        (DISABLED_TOOL,),
        (disabled_version,),
        (make_policy(5, 3),),
    )

    with pytest.raises(CapabilityUnavailableError):
        registry.resolve("query.disabled", INTERNAL)


def test_resolve_draft_only_raises_unavailable() -> None:
    registry, _loader = _build_registry(
        (DRAFT_TOOL,),
        (DRAFT_VERSION,),
        (make_policy(6, 2),),
    )

    with pytest.raises(CapabilityUnavailableError):
        registry.resolve("query.draft", INTERNAL)


def test_resolve_gray_only_without_stable_raises_unavailable() -> None:
    gray_only = make_version(
        22,
        2,
        implementation_ref="builtin.draft_tool.v2",
        is_stable=False,
    )
    registry, _loader = _build_registry((DRAFT_TOOL,), (gray_only,), (make_policy(6, 2),))

    with pytest.raises(CapabilityUnavailableError):
        registry.resolve("query.draft", INTERNAL)


def test_fresh_cache_serves_everything_when_database_unavailable() -> None:
    clock = FakeClock()
    registry, loader = _build_registry(
        (KPI, DRAFT_ACTION),
        (KPI_STABLE, DRAFT_ACTION_VERSION),
        (TOOL_DEFAULT_POLICY, ACTION_POLICY),
        clock=clock,
    )
    registry.resolve("query.kpi", INTERNAL)
    clock.advance(seconds=10)
    loader.failing = True

    resolved = registry.resolve("query.kpi", INTERNAL)
    action = registry.resolve("action.work_order.draft", INTERNAL)

    assert resolved.version_id == 11
    assert action.tool_key == "work_order_draft"


def test_stale_cache_rejects_actions() -> None:
    clock = FakeClock()
    registry, loader = _build_registry(
        (KPI, DRAFT_ACTION),
        (KPI_STABLE, DRAFT_ACTION_VERSION),
        (TOOL_DEFAULT_POLICY, ACTION_POLICY),
        clock=clock,
    )
    registry.resolve("query.kpi", INTERNAL)
    clock.advance(seconds=31)
    loader.failing = True

    with pytest.raises(RegistryUnavailableError):
        registry.resolve("action.work_order.draft", INTERNAL)


def test_stale_cache_forces_stable_for_query() -> None:
    clock = FakeClock()
    registry, loader = _build_registry(
        (KPI,),
        (KPI_STABLE, KPI_GRAY),
        (TOOL_DEFAULT_POLICY, GRAY_POLICY),
        clock=clock,
    )
    registry.resolve("query.kpi", INTERNAL)
    clock.advance(seconds=31)
    loader.failing = True

    resolved = registry.resolve("query.kpi", INTERNAL)

    assert resolved.version_id == 11
    assert resolved.selected_stable is True


def test_stale_snapshot_beyond_stale_window_raises_unavailable() -> None:
    clock = FakeClock()
    registry, loader = _build_registry(
        (KPI,),
        (KPI_STABLE,),
        (TOOL_DEFAULT_POLICY,),
        clock=clock,
        stale_query_ttl_seconds=60,
    )
    registry.resolve("query.kpi", INTERNAL)
    clock.advance(seconds=61)
    loader.failing = True

    with pytest.raises(RegistryUnavailableError):
        registry.resolve("query.kpi", INTERNAL)


def test_invalidate_forces_reload() -> None:
    registry, loader = _build_registry((KPI,), (KPI_STABLE,), (TOOL_DEFAULT_POLICY,))

    registry.resolve("query.kpi", INTERNAL)
    assert loader.calls == 1
    registry.invalidate()
    registry.resolve("query.kpi", INTERNAL)

    assert loader.calls == 2
