"""
load_prompt — Prompt 加载节点。

当请求指定了 prompt_code 时，从数据库加载当前激活版本的 Prompt。
如果指定 code 不存在或者未指定 prompt_code，则降级为系统默认 Prompt，
不中断对话流程。

变更说明：旧版本在此处抛 AppException 中断流程，新版本改为降级策略，
确保即使 Prompt 配置异常也能正常回复。
"""

from time import perf_counter

from app.runtime.schemas.trace_schema import TraceCreate
from app.runtime.services.prompt_service import prompt_service
from app.runtime.services.trace_service import trace_service
from app.runtime.state import RuntimeGraphState
from app.utils.ids import new_span_id

PROMPT_NODE_NAME = "load_active_prompt"


def load_prompt_node(state: RuntimeGraphState) -> RuntimeGraphState:
    """加载 active Prompt，如未指定或未找到则降级为系统默认 Prompt。"""
    prompt_code = state.get("prompt_code")
    if not prompt_code:
        # 未指定 Prompt code，直接跳过，call_llm 会使用 LlmClient 的系统 Prompt
        state["prompt"] = None
        state["prompt_fallback"] = False
        return state

    db = state["db"]
    trace_id = state["trace_id"]
    session_id = state["session_id"]
    conversation_id = state["conversation"].id
    graph_span_id = state["graph_span_id"]

    prompt_start = perf_counter()
    prompt = prompt_service.get_active_by_code(db, prompt_code)

    if prompt is None:
        # 指定 code 不存在：记录审计信息，降级为系统 Prompt，不中断会话
        trace_service.create(
            db,
            TraceCreate(
                trace_id=trace_id,
                span_id=new_span_id(),
                parent_span_id=graph_span_id,
                session_id=session_id,
                conversation_id=conversation_id,
                span_type="node",
                node_name=PROMPT_NODE_NAME,
                input_data={"prompt_code": prompt_code},
                output_data={
                    "prompt_found": False,
                    "fallback_to_system_prompt": True,
                    "requested_prompt_code": prompt_code,
                },
                cost_ms=max(1, int((perf_counter() - prompt_start) * 1000)),
                status="success",
            ),
        )
        state["prompt"] = None
        state["prompt_fallback"] = True
        return state

    # Prompt 加载成功，记录加载信息
    trace_service.create(
        db,
        TraceCreate(
            trace_id=trace_id,
            span_id=new_span_id(),
            parent_span_id=graph_span_id,
            session_id=session_id,
            conversation_id=conversation_id,
            span_type="node",
            node_name=PROMPT_NODE_NAME,
            input_data={"prompt_code": prompt_code},
            output_data={
                "prompt_found": True,
                "prompt_id": prompt.id,
                "prompt_code": prompt.code,
                "prompt_version": prompt.version,
            },
            cost_ms=max(1, int((perf_counter() - prompt_start) * 1000)),
            status="success",
        ),
    )

    state["prompt"] = prompt
    state["prompt_fallback"] = False
    return state
