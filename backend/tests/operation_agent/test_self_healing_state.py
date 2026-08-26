"""Operation 自修复状态契约与决策表测试。"""

from app.operation_agent.self_healing.constants import (
    FAILURE_ADVICE_MISSING,
    FAILURE_CONTENT_SAFETY,
    FAILURE_DEADLINE_INSUFFICIENT,
    FAILURE_HALLUCINATION,
    FAILURE_KEY_DATA_MISSING,
    FAILURE_REASON_MISSING,
    REPLAN_ADVICE,
    REPLAN_FALLBACK,
    REPLAN_REASON_AND_ADVICE,
    SH_DEGRADED,
    SH_EXHAUSTED,
    SH_NOT_RUN,
    SH_PASSED,
    SH_RECOVERED,
    default_self_healing,
)
from app.operation_agent.self_healing.decision import (
    build_repair_constraints,
    decide_replan_target,
)
from app.operation_agent.self_healing.state import (
    compute_api_status,
    get_self_healing,
    init_recovery_state,
    self_healing_from_record,
)
from app.operation_agent.state import OperationState


def test_default_self_healing_shape():
    sh = default_self_healing()
    assert sh == {
        "status": "not_run",
        "recovery_cycles": 0,
        "total_attempts": 0,
        "retried_operations": [],
        "replanned_target": None,
        "final_score": None,
        "fallback_used": False,
        "reason_codes": [],
    }


def test_get_self_healing_initializes_missing_state():
    state: OperationState = {"trace_id": "t1", "errors": []}
    sh = get_self_healing(state)
    assert sh["status"] == "not_run"
    assert state["self_healing"] is sh


def test_get_self_healing_preserves_existing_values():
    state: OperationState = {"self_healing": {"status": "recovered", "final_score": 0.9}}
    sh = get_self_healing(state)
    assert sh["status"] == "recovered"
    assert sh["final_score"] == 0.9
    assert sh["recovery_cycles"] == 0


def test_init_recovery_state_creates_containers():
    state: OperationState = {"trace_id": "t1"}
    init_recovery_state(state)
    assert state["recovery_context"] == {}
    assert state["evaluation_results"] == []
    assert state["recovery_events"] == []


def test_compute_api_status_rules():
    base: OperationState = {"final_answer": "## 报告", "errors": []}
    assert compute_api_status(base) == "success"

    recovered = {**base, "self_healing": {"status": SH_RECOVERED}}
    assert compute_api_status(recovered) == "success"

    recovered_with_errors = {
        **base,
        "self_healing": {"status": SH_RECOVERED},
        "errors": [{"node": "x", "message": "y"}],
    }
    assert compute_api_status(recovered_with_errors) == "partial"

    degraded = {**base, "self_healing": {"status": SH_DEGRADED}}
    assert compute_api_status(degraded) == "partial"

    exhausted = {**base, "self_healing": {"status": SH_EXHAUSTED}}
    assert compute_api_status(exhausted) == "partial"

    no_report = {"final_answer": "", "self_healing": {"status": SH_DEGRADED}}
    assert compute_api_status(no_report) == "failed"

    not_run_errors = {
        "final_answer": "## 报告",
        "errors": [{"node": "query", "message": "m"}],
        "self_healing": {"status": SH_NOT_RUN},
    }
    assert compute_api_status(not_run_errors) == "partial"


def test_decide_replan_target_table():
    assert decide_replan_target([FAILURE_ADVICE_MISSING]) == REPLAN_ADVICE
    assert decide_replan_target([FAILURE_REASON_MISSING]) == REPLAN_REASON_AND_ADVICE
    assert decide_replan_target([FAILURE_HALLUCINATION]) == REPLAN_REASON_AND_ADVICE
    assert decide_replan_target([FAILURE_CONTENT_SAFETY]) == REPLAN_FALLBACK
    assert decide_replan_target([FAILURE_KEY_DATA_MISSING]) == REPLAN_FALLBACK
    assert decide_replan_target([FAILURE_DEADLINE_INSUFFICIENT]) == REPLAN_FALLBACK
    assert decide_replan_target(["UNKNOWN_CODE"]) == REPLAN_FALLBACK
    assert decide_replan_target([]) == REPLAN_FALLBACK
    assert decide_replan_target([FAILURE_ADVICE_MISSING, FAILURE_HALLUCINATION]) == REPLAN_REASON_AND_ADVICE


def test_build_repair_constraints():
    constraints = build_repair_constraints(
        [FAILURE_ADVICE_MISSING],
        ["建议缺少动作"],
        "补充 action 字段",
    )
    assert constraints["replan_target"] == REPLAN_ADVICE
    assert constraints["critique"] == ["建议缺少动作"]
    assert constraints["repair_instruction"] == "补充 action 字段"


def test_self_healing_from_record_old_record_returns_not_run():
    class FakeRecord:
        self_healing_json = None

    sh = self_healing_from_record(FakeRecord())
    assert sh["status"] == SH_NOT_RUN


def test_self_healing_from_record_new_record():
    class FakeRecord:
        self_healing_json = {"status": SH_PASSED, "final_score": 0.9}

    sh = self_healing_from_record(FakeRecord())
    assert sh["status"] == SH_PASSED
    assert sh["final_score"] == 0.9
    assert sh["recovery_cycles"] == 0
