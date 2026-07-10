"""
InitContextNode — 初始化 State 的执行环境。

职责：
1. 生成全链路追踪 trace_id。
2. 根据 trigger_type 映射 analysis_mode。
3. 确保所有容器字段初始化为安全默认值。

该节点不调用 LLM，不查询数据库，不调用 Tool。
"""
from app.operation_agent.state import OperationState
from app.utils.ids import new_trace_id

# trigger_type → analysis_mode 映射表
_TRIGGER_MODE_MAP = {
    "page_load": "dashboard_snapshot",   # 页面加载 → 全局快照
    "tab_analysis": "domain_focus",      # Tab 切换 → 领域聚焦（默认）
    "expert_chat": "qa",                 # 专家问答 → QA 模式
    "scheduled_daily": "dashboard_snapshot",  # 定时任务 → 全局快照
}


def init_context_node(state: OperationState) -> OperationState:
    """初始化 State：设置 trace_id、analysis_mode，填充空容器。"""
    # API/SSE 入口已建立 trace 时必须沿用，保证 HTTP、Graph、持久化记录和
    # 流式 run_id 可以用同一个标识串联；直接调用 Graph 时再生成新 ID。
    if not state.get("trace_id"):
        state["trace_id"] = new_trace_id()
    trigger = state.get("trigger_type", "tab_analysis")
    state["analysis_mode"] = _TRIGGER_MODE_MAP.get(trigger, "domain_focus")

    # 确保所有容器字段存在，避免后续 Node 访问空值报错
    state.setdefault("user_context", {})
    state.setdefault("page_context", {})
    state["raw_data"] = {}
    state["metrics"] = []
    state["abnormal_items"] = []
    state["reason_analysis"] = ""
    state["risk_items"] = []
    state["advice_items"] = []
    state["evidence"] = []
    state["llm_usages"] = []
    state["errors"] = []
    state["final_answer"] = ""
    return state
