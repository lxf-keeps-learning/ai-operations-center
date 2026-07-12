"""
Report Chat Event Adapter — 将 LangGraph StreamPart 转换为 Report Chat SSE 事件。

映射规则：
  LangGraph 来源                      业务事件
  ──────────────────────────────    ─────────────────
  Stream Service 开始               message_started
  custom.kind=node_started          节点进度（可选跟踪）
  custom.kind=llm_token             answer_delta
  updates                           状态追踪（内部）
  values                            最终 State
  answer 校正（流式 vs 最终）         answer_reset + answer_delta
  正常完成                          message_completed（丰富元数据）
  异常                              message_failed
  流结束                            stream_closed

Report Chat SSE 协议：
  message_started → answer_delta* → [answer_reset → answer_delta] → message_completed → stream_closed

message_completed 元数据：
  message_id, conversation_id, session_id, question_scope, answer, answer_type,
  evidence_refs, query_scope, used_rag, rag_source_refs, rag_sources, errors
"""
from typing import Any

from app.report_chat_agent.state import ReportChatState


class ReportChatEventAdapter:
    """将 LangGraph astream 输出转换为 Report Chat SSE 事件。

    每个 process() 调用返回 0-N 个 (event_type, data_dict) 元组。
    在流结束后调用 finalize() 完成答案校正和 message_completed 生成。
    """

    def __init__(self, trace_id: str, session_id: str) -> None:
        self._trace_id = trace_id
        self._session_id = session_id
        self._sequence = 0
        self._final_state: ReportChatState | None = None
        self._streamed_parts: list[str] = []
        self._has_streamed = False

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    def _build(
        self,
        event_type: str,
        **extra: object,
    ) -> tuple[str, dict]:
        return (
            event_type,
            {
                "event_type": event_type,
                "sequence": self._next_seq(),
                "trace_id": self._trace_id,
                "session_id": self._session_id,
                **extra,
            },
        )

    def process(self, mode: str, data: Any) -> list[tuple[str, dict]]:
        """处理一条 LangGraph 流事件，返回 0-N 个 SSE 事件。"""
        if mode == "values":
            return self._process_values(data)
        elif mode == "custom":
            return self._process_custom(data)
        elif mode == "updates":
            return self._process_updates(data)
        return []

    def _process_values(self, data: Any) -> list[tuple[str, dict]]:
        if isinstance(data, dict):
            self._final_state = data
        return []

    def _process_custom(self, data: Any) -> list[tuple[str, dict]]:
        if not isinstance(data, dict):
            return []
        kind = data.get("kind")

        if kind == "llm_token":
            token = data.get("token", "")
            if not isinstance(token, str) or not token:
                return []
            self._streamed_parts.append(token)
            self._has_streamed = True
            return [self._build("answer_delta", delta=token)]

        return []

    def _process_updates(self, data: Any) -> list[tuple[str, dict]]:
        return []

    def get_message_started(self) -> tuple[str, dict]:
        return self._build("message_started", message="正在分析当前报告和相关依据")

    def finalize(self) -> list[tuple[str, dict]]:
        """在 Graph 执行完毕后调用，处理答案校正和 message_completed。"""
        events: list[tuple[str, dict]] = []
        fs = self._final_state

        if fs is None:
            return events

        final_answer = fs.get("final_answer", "")
        streamed_answer = "".join(self._streamed_parts)

        # 答案校正：当流式内容与 Graph 最终答案不一致时，重置并发送权威结果
        if final_answer and streamed_answer != final_answer:
            if self._has_streamed:
                events.append(self._build("answer_reset"))
            events.append(self._build("answer_delta", delta=final_answer))

        # message_completed 携带完整元数据
        evidence_refs = fs.get("evidence_refs", [])
        rag_source_refs = fs.get("rag_source_refs", [])
        rag_sources = fs.get("rag_sources", []) or fs.get("rag_results", [])
        query_scope = fs.get("query_scope", {})

        events.append(
            self._build(
                "message_completed",
                message_id=fs.get("message_id", ""),
                conversation_id=fs.get("conversation_id", ""),
                runtime_session_id=fs.get("runtime_session_id", ""),
                question_scope=fs.get("question_scope", "report_internal"),
                answer=final_answer,
                answer_type=fs.get("answer_type", "normal"),
                evidence_refs=evidence_refs,
                query_scope=query_scope,
                used_rag=fs.get("used_rag", False),
                rag_source_refs=rag_source_refs,
                rag_sources=rag_sources,
                errors=fs.get("errors", []),
            ),
        )

        return events

    def get_failed_event(self, error_message: str) -> tuple[str, dict]:
        return self._build(
            "message_failed",
            message="AI 深度解答生成失败",
            error_message=error_message,
        )

    def get_closed_event(self) -> tuple[str, dict]:
        return self._build("stream_closed")

    def get_final_state(self) -> ReportChatState | None:
        return self._final_state
