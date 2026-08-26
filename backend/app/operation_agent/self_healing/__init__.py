"""Operation Agent 自修复闭环（Evaluation / Reflection / Re-plan / 安全降级）。

公共导出：
  - 状态读写：get_self_healing / init_recovery_state / compute_api_status
  - 决策：decide_replan_target / build_repair_constraints
  - 事件：emit_recovery_event / record_operation_attempts
  - 常量：REPLAN_* / SH_* / EVENT_*
"""

from app.operation_agent.self_healing.constants import (
    EVENT_EVALUATION_COMPLETED,
    EVENT_FALLBACK_APPLIED,
    EVENT_REFLECTION_CREATED,
    EVENT_REPAIR_COMPLETED,
    EVENT_REPLAN_SELECTED,
    EVENT_RETRY_EXHAUSTED,
    EVENT_RETRY_SCHEDULED,
    EVENT_RETRY_STARTED,
    EVENT_RETRY_SUCCEEDED,
    REPLAN_ADVICE,
    REPLAN_FALLBACK,
    REPLAN_REASON_AND_ADVICE,
    SH_DEGRADED,
    SH_EXHAUSTED,
    SH_NOT_RUN,
    SH_PASSED,
    SH_RECOVERED,
)
from app.operation_agent.self_healing.decision import (
    build_repair_constraints,
    decide_replan_target,
)
from app.operation_agent.self_healing.events import (
    emit_recovery_event,
    record_operation_attempts,
    record_retried_operation,
)
from app.operation_agent.self_healing.state import (
    compute_api_status,
    get_self_healing,
    init_recovery_state,
    self_healing_from_record,
)

__all__ = [
    "EVENT_EVALUATION_COMPLETED",
    "EVENT_FALLBACK_APPLIED",
    "EVENT_REFLECTION_CREATED",
    "EVENT_REPAIR_COMPLETED",
    "EVENT_REPLAN_SELECTED",
    "EVENT_RETRY_EXHAUSTED",
    "EVENT_RETRY_SCHEDULED",
    "EVENT_RETRY_STARTED",
    "EVENT_RETRY_SUCCEEDED",
    "REPLAN_ADVICE",
    "REPLAN_FALLBACK",
    "REPLAN_REASON_AND_ADVICE",
    "SH_DEGRADED",
    "SH_EXHAUSTED",
    "SH_NOT_RUN",
    "SH_PASSED",
    "SH_RECOVERED",
    "build_repair_constraints",
    "compute_api_status",
    "decide_replan_target",
    "emit_recovery_event",
    "get_self_healing",
    "init_recovery_state",
    "record_operation_attempts",
    "record_retried_operation",
    "self_healing_from_record",
]
