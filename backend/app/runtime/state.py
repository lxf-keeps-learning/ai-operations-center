"""
Runtime Graph 状态定义 — 作为 Graph 中所有 Node 之间传递数据的唯一契约。

所有字段为可选（total=False），Node 在执行过程中逐步填充。
不保存 ORM 连接或不可序列化对象。
"""

from typing import Any, TypedDict


class RuntimeGraphState(TypedDict, total=False):
    """Runtime Graph 的 State 类型

    — 输入参数（由 service 层在 invoke 前设置） —
    db:               SQLAlchemy Session（来自 API 层依赖注入）
    user_id:          用户 ID
    message:          用户输入的消息
    conversation_id:  会话 ID（None 时自动创建新会话）
    biz_type:         业务类型（如 alarm / operation 等）
    prompt_code:      指定使用的 Prompt 模板编码

    — 由 init_session_node 填充 —
    conversation:     ConversationResponse
    history_messages: 按 user/assistant 格式拼接的历史消息列表
    session:          SessionResponse
    session_id:       Session ID
    trace_id:         全链路追踪 ID
    root_span_id:     runtime 层根 Span ID
    graph_span_id:    graph 编排层 Span ID

    — 由 load_prompt_node 填充 —
    prompt:           PromptResponse（未指定 prompt_code 时为 None）
    prompt_fallback:  True 表示指定 code 未找到，已降级为系统默认 Prompt

    — 由 call_llm_node 填充 —
    llm_result:       LlmResult（含 content、tokens、耗时等）
    answer:           LLM 返回的文本回答
    """
    db: Any
    user_id: str
    message: str
    conversation_id: str | None
    biz_type: str | None
    prompt_code: str | None

    conversation: Any
    history_messages: list[dict[str, str]]
    session: Any
    session_id: str
    trace_id: str
    root_span_id: str
    graph_span_id: str

    prompt: Any
    prompt_fallback: bool

    llm_result: Any
    answer: str
