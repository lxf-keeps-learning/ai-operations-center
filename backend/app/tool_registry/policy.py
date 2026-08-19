from __future__ import annotations

from dataclasses import dataclass

from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import GovernanceDecision, ToolPolicyRecord


@dataclass(frozen=True)
class EffectivePolicy:
    policy_id: int
    decision: GovernanceDecision
    rate_limit_per_minute: int
    gray_percentage: int
    requires_confirmation: bool


def resolve_policy(
    policies: tuple[ToolPolicyRecord, ...] | list[ToolPolicyRecord],
    version_id: int,
    context: ToolContext,
) -> EffectivePolicy:
    matches = [
        policy
        for policy in policies
        if _matches(policy, version_id=version_id, context=context)
    ]
    if not matches:
        raise ValueError(f"no matching policy for version_id={version_id}")

    winner = sorted(matches, key=_sort_key, reverse=True)[0]
    return EffectivePolicy(
        policy_id=winner.id,
        decision=winner.decision,
        rate_limit_per_minute=winner.rate_limit_per_minute,
        gray_percentage=winner.gray_percentage,
        requires_confirmation=winner.requires_confirmation,
    )


def _matches(policy: ToolPolicyRecord, *, version_id: int, context: ToolContext) -> bool:
    return (
        (policy.version_id is None or policy.version_id == version_id)
        and (policy.tenant_id is None or policy.tenant_id == context.tenant_id)
        and (policy.role is None or policy.role == context.role)
    )


def _sort_key(policy: ToolPolicyRecord) -> tuple[int, int, int, int, int]:
    return (
        int(policy.version_id is not None),
        int(policy.tenant_id is not None),
        int(policy.role is not None),
        int(policy.decision is GovernanceDecision.DENY),
        -policy.id,
    )
