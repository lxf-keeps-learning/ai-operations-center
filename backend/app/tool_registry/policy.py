from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import GovernanceDecision, ToolPolicyRecord


@dataclass(frozen=True)
class EffectivePolicy:
    policy_id: int
    decision: GovernanceDecision
    rate_limit_per_minute: int
    gray_percentage: int
    requires_confirmation: bool


class PolicyRank(IntEnum):
    VERSION_TENANT_ROLE = 4
    VERSION_DEFAULT = 3
    TOOL_TENANT_ROLE = 2
    TOOL_DEFAULT = 1


def resolve_policy(
    policies: tuple[ToolPolicyRecord, ...] | list[ToolPolicyRecord],
    version_id: int,
    context: ToolContext,
) -> EffectivePolicy:
    matches = []
    for policy in policies:
        rank = _match_rank(policy, version_id=version_id, context=context)
        if rank is not None:
            matches.append((rank, policy))
    if not matches:
        raise ValueError(f"no matching policy for version_id={version_id}")

    resolved_rank = max(rank for rank, _policy in matches)
    resolved_candidates = [policy for rank, policy in matches if rank == resolved_rank]
    deny_candidates = [
        policy for policy in resolved_candidates if policy.decision is GovernanceDecision.DENY
    ]
    winner = max(deny_candidates or resolved_candidates, key=lambda policy: policy.id)
    return EffectivePolicy(
        policy_id=winner.id,
        decision=winner.decision,
        rate_limit_per_minute=winner.rate_limit_per_minute,
        gray_percentage=winner.gray_percentage,
        requires_confirmation=winner.requires_confirmation,
    )


def _match_rank(
    policy: ToolPolicyRecord,
    *,
    version_id: int,
    context: ToolContext,
) -> PolicyRank | None:
    if (
        policy.version_id == version_id
        and policy.tenant_id == context.tenant_id
        and policy.role == context.role
        and context.tenant_id is not None
        and context.role is not None
    ):
        return PolicyRank.VERSION_TENANT_ROLE

    if policy.version_id == version_id and policy.tenant_id is None and policy.role is None:
        return PolicyRank.VERSION_DEFAULT

    if (
        policy.version_id is None
        and policy.tenant_id == context.tenant_id
        and policy.role == context.role
        and context.tenant_id is not None
        and context.role is not None
    ):
        return PolicyRank.TOOL_TENANT_ROLE

    if policy.version_id is None and policy.tenant_id is None and policy.role is None:
        return PolicyRank.TOOL_DEFAULT

    return None
