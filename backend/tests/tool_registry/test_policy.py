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
        version_id=12,
        tenant_id="t1",
        role=None,
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
        tenant_id="t1",
        role="operator",
        decision=GovernanceDecision.DENY,
        rate_limit_per_minute=1,
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


def test_matching_deny_is_final_at_same_specificity() -> None:
    result = resolve_policy(
        POLICIES,
        version_id=12,
        context=ToolContext(tenant_id="t1", role="operator"),
    )

    assert result.policy_id == 5
    assert result.decision is GovernanceDecision.DENY


def test_falls_back_to_less_specific_matching_policy() -> None:
    result = resolve_policy(
        POLICIES[:4],
        version_id=12,
        context=ToolContext(tenant_id="t1", role="viewer"),
    )

    assert result.policy_id == 3
    assert result.requires_confirmation is True
