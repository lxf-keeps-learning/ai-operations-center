from app.operation_agent.state import OperationState
from app.utils.ids import new_trace_id

_TRIGGER_MODE_MAP = {
    "page_load": "dashboard_snapshot",
    "tab_analysis": "domain_focus",
    "expert_chat": "qa",
    "scheduled_daily": "dashboard_snapshot",
}


def init_context_node(state: OperationState) -> OperationState:
    state["trace_id"] = new_trace_id()
    trigger = state.get("trigger_type", "tab_analysis")
    state["analysis_mode"] = _TRIGGER_MODE_MAP.get(trigger, "domain_focus")
    state.setdefault("user_context", {})
    state.setdefault("page_context", {})
    state["raw_data"] = {}
    state["metrics"] = []
    state["abnormal_items"] = []
    state["reason_analysis"] = ""
    state["risk_items"] = []
    state["advice_items"] = []
    state["evidence"] = []
    state["errors"] = []
    state["final_answer"] = ""
    return state
