"""Declarative contracts for operation-analysis business agents."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainAgentSpec:
    """Immutable configuration shared by a domain agent's reason/advice steps."""

    key: str
    label: str
    reason_prompt: str
    advice_prompt: str
    reason_action_type: str
    advice_action_type: str


DOMAIN_AGENT_SPECS: dict[str, DomainAgentSpec] = {
    "safety": DomainAgentSpec(
        key="safety",
        label="本质安全",
        reason_prompt="domains/safety_analysis.md",
        advice_prompt="domains/safety_advice.md",
        reason_action_type="safety_reason",
        advice_action_type="safety_advice",
    ),
    "maintenance": DomainAgentSpec(
        key="maintenance",
        label="设备运维",
        reason_prompt="domains/maintenance_analysis.md",
        advice_prompt="domains/maintenance_advice.md",
        reason_action_type="maintenance_reason",
        advice_action_type="maintenance_advice",
    ),
    "business": DomainAgentSpec(
        key="business",
        label="经营改善",
        reason_prompt="domains/business_analysis.md",
        advice_prompt="domains/business_advice.md",
        reason_action_type="business_reason",
        advice_action_type="business_advice",
    ),
    "capability": DomainAgentSpec(
        key="capability",
        label="能力提升",
        reason_prompt="domains/capability_analysis.md",
        advice_prompt="domains/capability_advice.md",
        reason_action_type="capability_reason",
        advice_action_type="capability_advice",
    ),
    "all": DomainAgentSpec(
        key="all",
        label="全域分析",
        reason_prompt="domains/all_analysis.md",
        advice_prompt="domains/all_advice.md",
        reason_action_type="all_reason",
        advice_action_type="all_advice",
    ),
}
