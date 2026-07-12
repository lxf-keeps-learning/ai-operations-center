"""
call_llm — LLM 调用节点。

负责：
  1. 记录上下文查询 Tool Span（历史消息）
  2. 调用 LLM（流式 stream_chat 或 同步 chat）
  3. 记录 LLM 调用 Span（含 model、tokens、耗时等）

流式场景下，LLM 的 token 通过 get_stream_writer() 以 custom 事件实时回传；
非流式场景下直接调用 chat() 获取完整回复。
"""
from time import perf_counter

from langgraph.config import get_stream_writer

from app.core.config.llm_settings import llm_settings
from app.runtime.llm.client import llm_client
from app.runtime.schemas.trace_schema import TraceCreate
from app.runtime.services.trace_service import trace_service
from app.runtime.state import RuntimeGraphState
from app.utils.ids import new_span_id

# Trace 中 tool_name 字段的值，表示历史消息上下文来源
CONTEXT_TOOL_NAME = "mysql_conversation_history"


def _stream_writer_or_none():
    """取得 LangGraph writer；节点被独立调用时返回 None。"""
    try:
        return get_stream_writer()
    except RuntimeError:
        return None


def call_llm_node(state: RuntimeGraphState) -> RuntimeGraphState:
    """记录工具 Span，调用 LLM，记录 LLM Span。"""
    db = state["db"]
    trace_id = state["trace_id"]
    session_id = state["session_id"]
    conversation_id = state["conversation"].id
    graph_span_id = state["graph_span_id"]
    message = state["message"]
    history_messages = state["history_messages"]
    prompt = state.get("prompt")
    prompt_fallback = state.get("prompt_fallback", False)
    requested_prompt_code = state.get("prompt_code")

    # ── 记录上下文 Tool Span（历史消息查询视为一次 Tool 调用） ──
    tool_start = perf_counter()
    trace_service.create(
        db,
        TraceCreate(
            trace_id=trace_id,
            span_id=new_span_id(),
            parent_span_id=graph_span_id,
            session_id=session_id,
            conversation_id=conversation_id,
            span_type="tool",
            tool_name=CONTEXT_TOOL_NAME,
            input_data={"conversation_id": conversation_id, "session_id": session_id},
            output_data={
                "context_source": "mysql_session_json",
                "history_messages": len(history_messages),
            },
            cost_ms=max(1, int((perf_counter() - tool_start) * 1000)),
            status="success",
        ),
    )

    # ── 调用 LLM ──
    # 在 astream 模式下用 get_stream_writer() 实时回传 token
    # 在 invoke 模式下直接调用 chat()（不流式输出 token）
    writer = _stream_writer_or_none() if state.get("_streaming") else None

    if writer is not None:
        def on_chunk(text: str) -> None:
            writer({
                "kind": "llm_token",
                "token": text,
            })
        llm_result = llm_client.stream_chat(
            prompt.content if prompt else None,
            message,
            on_chunk=on_chunk,
            history=history_messages,
        )
    else:
        llm_result = llm_client.chat(
            prompt.content if prompt else None,
            message,
            history=history_messages,
        )

    # LLM 失败时生成友好的替代回答
    answer = (
        llm_result.content
        if llm_result.success
        else f"（AI 回复失败：{llm_result.error_message or '未知错误'}）"
    )

    # ── 记录 LLM 调用 Span ──
    trace_service.create(
        db,
        TraceCreate(
            trace_id=trace_id,
            span_id=new_span_id(),
            parent_span_id=graph_span_id,
            session_id=session_id,
            conversation_id=conversation_id,
            span_type="llm",
            model_name=llm_result.model or llm_settings.default_provider,
            prompt_id=prompt.id if prompt else None,
            prompt_code=prompt.code if prompt else requested_prompt_code,
            prompt_version=prompt.version if prompt else None,
            prompt_snapshot=llm_result.system_prompt or (prompt.content if prompt else None),
            input_data={
                "input": message,
                "history_messages": len(history_messages),
                "requested_prompt_code": requested_prompt_code,
                "fallback_to_system_prompt": prompt_fallback,
            },
            output_data={
                "output": answer,
                "provider": "deepseek",
                "model": llm_result.model,
            },
            cost_ms=llm_result.cost_ms,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            status="success" if llm_result.success else "failed",
            error_code=None if llm_result.success else "LLM_PROVIDER_ERROR",
            error_message=None if llm_result.success else llm_result.error_message,
        ),
    )

    state["llm_result"] = llm_result
    state["answer"] = answer
    return state
