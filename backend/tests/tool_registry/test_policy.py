from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import GovernanceDecision, ToolPolicyRecord
from app.tool_registry.policy import EffectivePolicy, resolve_policy


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
        rate_limit_per_minute=45,
        gray_percentage=10,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=3,
        tool_id=1,
        version_id=None,
        tenant_id="t1",
        role="viewer",
        decision=GovernanceDecision.ALLOW,
        rate_limit_per_minute=30,
        gray_percentage=25,
        requires_confirmation=True,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=4,
        tool_id=1,
        version_id=12,
        tenant_id="t1",
        role="operator",
        decision=GovernanceDecision.ALLOW,
        rate_limit_per_minute=15,
        gray_percentage=50,
        requires_confirmation=True,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=5,
        tool_id=1,
        version_id=12,
        tenant_id=None,
        role=None,
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=1,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=6,
        tool_id=1,
        version_id=12,
        tenant_id="t1",
        role="operator",
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=2,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=7,
        tool_id=1,
        version_id=12,
        tenant_id="t1",
        role=None,
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=3,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=8,
        tool_id=1,
        version_id=12,
        tenant_id=None,
        role="operator",
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=4,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=9,
        tool_id=1,
        version_id=None,
        tenant_id="t1",
        role=None,
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=5,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
    ToolPolicyRecord(
        id=10,
        tool_id=1,
        version_id=None,
        tenant_id=None,
        role="operator",
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=6,
        gray_percentage=0,
        requires_confirmation=False,
        enabled=True,
    ),
)


def test_version_tenant_role_policy_wins() -> None:
    result = resolve_policy(
        POLICIES[:4],
        version_id=12,
        context=ToolContext(tenant_id="t1", role="operator"),
    )

    assert result == EffectivePolicy(
        policy_id=4,
        decision=GovernanceDecision.ALLOW,
        rate_limit_per_minute=15,
        gray_percentage=50,
        requires_confirmation=True,
    )


def test_version_default_beats_unsupported_partial_version_scope() -> None:
    result = resolve_policy(
        (POLICIES[0], POLICIES[1], POLICIES[6], POLICIES[7]),
        version_id=12,
        context=ToolContext(tenant_id="t1", role="unknown"),
    )

    assert result.policy_id == 2
    assert result.decision is GovernanceDecision.ALLOW


def test_matching_deny_is_final_at_same_rank() -> None:
    result = resolve_policy(
        POLICIES[:6],
        version_id=12,
        context=ToolContext(tenant_id="t1", role="operator"),
    )

    assert result.policy_id == 6
    assert result.decision is GovernanceDecision.DENY


def test_version_default_rank_matches_when_no_version_tenant_role_policy_exists() -> None:
    result = resolve_policy(
        POLICIES[:3],
        version_id=12,
        context=ToolContext(tenant_id="t1", role="viewer"),
    )

    assert result.policy_id == 2
    assert result.requires_confirmation is False


def test_tool_tenant_role_rank_matches_when_version_scope_is_absent() -> None:
    result = resolve_policy(
        (POLICIES[0], POLICIES[2]),
        version_id=99,
        context=ToolContext(tenant_id="t1", role="viewer"),
    )

    assert result.policy_id == 3
    assert result.requires_confirmation is True


def test_tool_default_rank_matches_as_last_resort() -> None:
    result = resolve_policy(
        (POLICIES[0],),
        version_id=99,
        context=ToolContext(tenant_id="other", role="viewer"),
    )

    assert result.policy_id == 1
    assert result.decision is GovernanceDecision.ALLOW


def test_unsupported_partial_shapes_never_match() -> None:
    result = resolve_policy(
        POLICIES,
        version_id=99,
        context=ToolContext(tenant_id="t1", role="operator"),
    )

    assert result.policy_id == 1
