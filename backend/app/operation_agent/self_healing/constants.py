"""Operation 自修复常量与默认值。"""

from __future__ import annotations

from typing import Any

# ── self_healing.status 取值 ────────────────────────────────────
SH_PASSED = "passed"
SH_RECOVERED = "recovered"
SH_DEGRADED = "degraded"
SH_EXHAUSTED = "exhausted"
SH_NOT_RUN = "not_run"

VALID_STATUSES = {SH_PASSED, SH_RECOVERED, SH_DEGRADED, SH_EXHAUSTED, SH_NOT_RUN}

# ── Re-plan 目标 ────────────────────────────────────────────────
REPLAN_ADVICE = "advice"
REPLAN_REASON_AND_ADVICE = "reason_and_advice"
REPLAN_FALLBACK = "fallback"

VALID_REPLAN_TARGETS = {REPLAN_ADVICE, REPLAN_REASON_AND_ADVICE, REPLAN_FALLBACK}

# ── 评估 failure_codes ──────────────────────────────────────────
FAILURE_REASON_MISSING = "REASON_MISSING"
FAILURE_REASON_FALLBACK_PLACEHOLDER = "REASON_FALLBACK_PLACEHOLDER"
FAILURE_ADVICE_MISSING = "ADVICE_MISSING"
FAILURE_ADVICE_INCOMPLETE_FIELDS = "ADVICE_INCOMPLETE_FIELDS"
FAILURE_ADVICE_INVALID_PRIORITY = "ADVICE_INVALID_PRIORITY"
FAILURE_ADVICE_NO_EVIDENCE = "ADVICE_NO_EVIDENCE"
FAILURE_ADVICE_EVIDENCE_UNGROUNDED = "ADVICE_EVIDENCE_UNGROUNDED"
FAILURE_DATA_GROUNDING = "DATA_GROUNDING_FAILED"
FAILURE_HALLUCINATION = "HALLUCINATION"
FAILURE_REASON_INSUFFICIENT = "REASON_INSUFFICIENT"
FAILURE_ADVICE_NOT_ACTIONABLE = "ADVICE_NOT_ACTIONABLE"
FAILURE_CONTENT_SAFETY = "CONTENT_SAFETY_BLOCKED"
FAILURE_KEY_DATA_MISSING = "KEY_DATA_MISSING"
FAILURE_DEADLINE_INSUFFICIENT = "DEADLINE_INSUFFICIENT"
FAILURE_JUDGE_UNAVAILABLE = "JUDGE_UNAVAILABLE"

# ── 可观测事件类型 ──────────────────────────────────────────────
EVENT_RETRY_SCHEDULED = "retry_scheduled"
EVENT_RETRY_STARTED = "retry_started"
EVENT_RETRY_SUCCEEDED = "retry_succeeded"
EVENT_RETRY_EXHAUSTED = "retry_exhausted"
EVENT_EVALUATION_COMPLETED = "evaluation_completed"
EVENT_REFLECTION_CREATED = "reflection_created"
EVENT_REPLAN_SELECTED = "replan_selected"
EVENT_REPAIR_COMPLETED = "repair_completed"
EVENT_FALLBACK_APPLIED = "fallback_applied"


def default_self_healing() -> dict[str, Any]:
    """返回标准 self_healing 结构（全字段 JSON 可序列化）。"""
    return {
        "status": SH_NOT_RUN,
        "recovery_cycles": 0,
        "total_attempts": 0,
        "retried_operations": [],
        "replanned_target": None,
        "final_score": None,
        "fallback_used": False,
        "reason_codes": [],
    }


# 规则兜底 / 内容安全 / 关键数据缺失 / 预算不足 的降级原因（不调用 Judge）。
# 键为 reason_codes 值，值用于可读说明（不持久化敏感信息）。
DEGRADED_REASON_HINTS: dict[str, str] = {
    "RULE_FALLBACK_USED": "已使用规则兜底，跳过 Judge",
    FAILURE_CONTENT_SAFETY: "内容安全拦截，跳过 Judge",
    "RETRY_EXHAUSTED": "Tool/LLM 重试已耗尽，标记降级",
    FAILURE_KEY_DATA_MISSING: "关键数据缺失，跳过 Judge",
    FAILURE_DEADLINE_INSUFFICIENT: "剩余预算不足以完成修复，跳过 Judge",
    FAILURE_JUDGE_UNAVAILABLE: "Judge 不可用，fail-open 保留当前输出",
}
