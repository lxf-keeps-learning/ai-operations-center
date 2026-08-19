from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import (
    ActionPhase,
    GovernanceDecision,
    ToolDefinitionRecord,
    ToolPolicyRecord,
    ToolType,
    ToolVersionRecord,
    VersionStatus,
)
from app.tool_registry.rollout import VersionSelection, choose_version, gray_bucket


TOOL = ToolDefinitionRecord(
    id=1,
    tool_key="kpi_query",
    capability="query.kpi",
    name="KPI Query",
    description="Returns KPI data",
    tool_type=ToolType.QUERY,
    action_phase=None,
    enabled=True,
)

STABLE_VERSION = ToolVersionRecord(
    id=11,
    tool_id=1,
    version="1.0.0",
    implementation_ref="builtin.kpi_query",
    input_schema={"type": "object"},
    output_schema={"type": "object"},
    status=VersionStatus.PUBLISHED,
    is_stable=True,
)

GRAY_VERSION = ToolVersionRecord(
    id=12,
    tool_id=1,
    version="1.1.0",
    implementation_ref="builtin.kpi_query.v110",
    input_schema={"type": "object"},
    output_schema={"type": "object"},
    status=VersionStatus.PUBLISHED,
    is_stable=False,
)

POLICIES = (
    ToolPolicyRecord(
        id=1,
        tool_id=1,
        version_id=None,
        tenant_id=None,
        role=None,
        decision=GovernanceDecision.ALLOW,
        rate_limit_per_minute=60,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=2,
        tool_id=1,
        version_id=12,
        tenant_id=None,
        role=None,
        decision=GovernanceDecision.ALLOW,
        rate_limit_per_minute=60,
        gray_percentage=100,
        requires_confirmation=False,
        enabled=True,
    ),
)


def test_gray_bucket_is_stable() -> None:
    assert gray_bucket("kpi_query", "tenant-a") == gray_bucket("kpi_query", "tenant-a")
    assert gray_bucket("kpi_query", "tenant-a") == 12
    assert 0 <= gray_bucket("kpi_query", "tenant-a") <= 99


def test_missing_tenant_always_selects_stable() -> None:
    result = choose_version(
        TOOL,
        (STABLE_VERSION, GRAY_VERSION),
        POLICIES,
        ToolContext(),
    )

    assert result == VersionSelection(
        version_id=11,
        version="1.0.0",
        implementation_ref="builtin.kpi_query",
        gray_bucket=None,
        selected_stable=True,
    )


def test_gray_hit_selects_non_stable_version() -> None:
    result = choose_version(
        TOOL,
        (STABLE_VERSION, GRAY_VERSION),
        POLICIES,
        ToolContext(tenant_id="tenant-a"),
    )

    assert result.version_id == 12
    assert result.selected_stable is False
    assert result.gray_bucket == 12


def test_stable_only_ignores_gray_rollout() -> None:
    result = choose_version(
        TOOL,
        (STABLE_VERSION, GRAY_VERSION),
        POLICIES,
        ToolContext(tenant_id="tenant-a"),
        stable_only=True,
    )

    assert result.version_id == 11
    assert result.selected_stable is True
