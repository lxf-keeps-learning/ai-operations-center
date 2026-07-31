from typing import Any


def build_business_content(version: Any) -> str:
    parts: list[str] = []
    if version.business_role_content:
        parts.append(version.business_role_content)
    if version.business_goal_content:
        parts.append(version.business_goal_content)
    if version.business_rules:
        parts.append("## 业务规则")
        for index, rule in enumerate(version.business_rules, 1):
            if isinstance(rule, dict):
                if rule.get("enabled", True):
                    parts.append(f"{index}. {rule.get('content', '')}")
            else:
                parts.append(f"{index}. {rule}")
    if version.output_requirement:
        parts.append(version.output_requirement)
    if version.positive_examples:
        parts.append("## 正例")
        for example in version.positive_examples:
            content = example.get("content", "") if isinstance(example, dict) else example
            parts.append(f"- {content}")
    if version.negative_examples:
        parts.append("## 反例")
        for example in version.negative_examples:
            content = example.get("content", "") if isinstance(example, dict) else example
            parts.append(f"- {content}")
    return "\n\n".join(parts)
