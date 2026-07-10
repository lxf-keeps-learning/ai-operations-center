"""
init_session — 会话初始化节点。

Graph 的第一个节点，负责：
  1. 校验或自动创建 Conversation
  2. 查询最近历史消息（供 LLM 多轮对话上下文使用）
  3. 创建 Session（状态 running）
  4. 生成 trace_id、span_id，记录 runtime 根 Span 和 graph 编排 Span
"""

from app.core.exception.base_exception import AppException
from app.core.exception.error_code import CONVERSATION_CLOSED, CONVERSATION_NOT_FOUND
from app.runtime.schemas.conversation_schema import ConversationCreate
from app.runtime.schemas.session_schema import SessionCreate
from app.runtime.schemas.status import CONV_ACTIVE, CONV_CREATED, SESS_RUNNING
from app.runtime.schemas.trace_schema import TraceCreate
from app.runtime.services.conversation_service import conversation_service
from app.runtime.services.session_service import session_service
from app.runtime.services.trace_service import trace_service
from app.runtime.state import RuntimeGraphState
from app.utils.ids import new_span_id, new_trace_id

# Trace 中 graph_name 字段的值，用于全链路追踪标识
RUNTIME_GRAPH_NAME = "ioc_runtime_chat_graph"


def init_session_node(state: RuntimeGraphState) -> RuntimeGraphState:
    """初始化会话上下文并记录全链路追踪起始 Span。"""
    db = state["db"]
    user_id = state["user_id"]
    message = state["message"]
    conversation_id = state.get("conversation_id")
    biz_type = state.get("biz_type")

    # ── 校验或自动创建 Conversation ──
    conv = None
    if conversation_id:
        conv = conversation_service.get_by_id(db, conversation_id)
        if conv is None:
            raise AppException.from_error_code(
                CONVERSATION_NOT_FOUND,
                message=f"会话 {conversation_id} 不存在",
            )
        if conv.status not in (CONV_ACTIVE, CONV_CREATED):
            raise AppException.from_error_code(
                CONVERSATION_CLOSED,
                message=f"会话 {conversation_id} 状态为 {conv.status}，无法继续对话",
            )
    if conv is None:
        conv = conversation_service.create(
            db, ConversationCreate(user_id=user_id, title=message[:100], biz_type=biz_type)
        )
    conversation_id = conv.id

    # ── 查询历史消息（多轮对话上下文） ──
    history_messages = session_service.list_recent_messages(db, conversation_id)

    # ── 创建运行记录 Session（running） ──
    sess = session_service.create(
        db,
        SessionCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            input_text=message,
            task_type="chat",
            context={
                "biz_type": biz_type,
                "prompt_code": state.get("prompt_code"),
                "history_messages": len(history_messages),
            },
            status=SESS_RUNNING,
        ),
    )

    # ── 生成追踪 ID 并记录全链路 Span ──
    trace_id = new_trace_id()

    # runtime 层根 Span（整次请求的总入口）
    root_span_id = new_span_id()
    trace_service.create(
        db,
        TraceCreate(
            trace_id=trace_id,
            span_id=root_span_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="runtime",
            input_data={"event": "session_created", "user_id": user_id},
            output_data={"conversation_id": conversation_id, "session_id": sess.id},
            status="success",
        ),
    )

    # graph 编排层 Span（作为后续所有 node/tool/llm span 的父 span）
    graph_span_id = new_span_id()
    trace_service.create(
        db,
        TraceCreate(
            trace_id=trace_id,
            span_id=graph_span_id,
            parent_span_id=root_span_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="graph",
            graph_name=RUNTIME_GRAPH_NAME,
            input_data={"message": message, "biz_type": biz_type},
            output_data={"nodes": ["init_session", "load_prompt", "call_llm", "finalize"]},
            status="success",
        ),
    )

    # ── 将中间结果写回 State ──
    state["conversation"] = conv
    state["history_messages"] = history_messages
    state["session"] = sess
    state["session_id"] = sess.id
    state["trace_id"] = trace_id
    state["root_span_id"] = root_span_id
    state["graph_span_id"] = graph_span_id

    return state
