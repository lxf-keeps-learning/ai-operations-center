"""Re-plan 决策表与评估结果判定工具。

Reflection（reflect 节点）不额外调用 LLM，只把 Judge / 确定性评估结果
转换为结构化修订约束；Re-plan 使用固定决策表选择修复路径。
"""

from __future__ import annotations

from typing import Any

from app.operation_agent.self_healing.constants import (
    FAILURE_ADVICE_EVIDENCE_UNGROUNDED,
    FAILURE_ADVICE_INCOMPLETE_FIELDS,
    FAILURE_ADVICE_INVALID_PRIORITY,
    FAILURE_ADVICE_MISSING,
    FAILURE_ADVICE_NOT_ACTIONABLE,
    FAILURE_ADVICE_NO_EVIDENCE,
    FAILURE_CONTENT_SAFETY,
    FAILURE_DATA_GROUNDING,
    FAILURE_DEADLINE_INSUFFICIENT,
    FAILURE_HALLUCINATION,
    FAILURE_KEY_DATA_MISSING,
    FAILURE_REASON_FALLBACK_PLACEHOLDER,
    FAILURE_REASON_INSUFFICIENT,
    FAILURE_REASON_MISSING,
    REPLAN_ADVICE,
    REPLAN_FALLBACK,
    REPLAN_REASON_AND_ADVICE,
)

# 建议侧失败 → 只修订 advice
_ADVICE_FAILURES = {
    FAILURE_ADVICE_MISSING,
    FAILURE_ADVICE_INCOMPLETE_FIELDS,
    FAILURE_ADVICE_INVALID_PRIORITY,
    FAILURE_ADVICE_NO_EVIDENCE,
    FAILURE_ADVICE_EVIDENCE_UNGROUNDED,
    FAILURE_ADVICE_NOT_ACTIONABLE,
}

# 原因侧失败 → 修订 reason + advice
_REASON_FAILURES = {
    FAILURE_REASON_MISSING,
    FAILURE_REASON_FALLBACK_PLACEHOLDER,
    FAILURE_DATA_GROUNDING,
    FAILURE_HALLUCINATION,
    FAILURE_REASON_INSUFFICIENT,
}

# 不可修复 → 安全降级
_NON_REPAIRABLE_FAILURES = {
    FAILURE_CONTENT_SAFETY,
    FAILURE_KEY_DATA_MISSING,
    FAILURE_DEADLINE_INSUFFICIENT,
}


def decide_replan_target(failure_codes: list[str] | None) -> str:
    """固定决策表：failure_codes → replan_target。

    - 建议格式/字段/证据引用/可执行性失败 → advice
    - 原因依据不足/逻辑问题/幻觉 → reason_and_advice
    - 内容安全/关键数据缺失/Deadline 不足 → fallback
    - 未识别的问题 → fallback
    """
    codes = set(failure_codes or [])
    if not codes:
        return REPLAN_FALLBACK
    if codes & _NON_REPAIRABLE_FAILURES:
        return REPLAN_FALLBACK
    if codes & _REASON_FAILURES:
        return REPLAN_REASON_AND_ADVICE
    if codes & _ADVICE_FAILURES:
        return REPLAN_ADVICE
    return REPLAN_FALLBACK


def build_repair_constraints(
    failure_codes: list[str] | None,
    critique: list[str] | None,
    repair_instruction: str | None,
) -> dict[str, Any]:
    """Reflection：把评估结果转换为结构化修订约束（不保存模型思维过程）。"""
    return {
        "failure_codes": list(failure_codes or []),
        "critique": list(critique or []),
        "repair_instruction": repair_instruction or "",
        "replan_target": decide_replan_target(failure_codes),
    }
