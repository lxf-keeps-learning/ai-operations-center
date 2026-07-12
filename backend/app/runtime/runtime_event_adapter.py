"""
Runtime Event Adapter — 将 LangGraph StreamPart 转换为 Runtime SSE 事件。

映射规则：
  LangGraph 来源               业务事件
  ──────────────────────────  ─────────────────
  Stream Service 开始          message_started
  custom.kind=llm_token       token
  custom.kind=node_started    （可选进度，当前不向客户发送）
  updates                     状态追踪（内部）
  values                      最终 State → message_completed
  异常                         message_failed
  流结束                       stream_closed

Runtime SSE 协议：
  message_started → token* → message_completed → stream_closed
  异常：message_started → message_failed → stream_closed
"""
from typing import Any

from app.runtime.state import RuntimeGraphState


class RuntimeEventAdapter:
    """将 LangGraph astream 输出转换为 Runtime SSE 事件。

    每个 process() 调用返回 0-N 个 (event_type, data_dict) 元组。
    """

    def __init__(self) -> None:
        self._has_started = False
        self._final_state: RuntimeGraphState | None = None
        self._tokens: list[str] = []
        self._token_count = 0

    def process(self, mode: str, data: Any) -> list[tuple[str, dict]]:
        """处理一条 LangGraph 流事件，返回 0-N 个 (event_type, data) 元组。"""
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
            self._tokens.append(token)
            self._token_count += 1
            return [("token", {"delta": token})]

        return []

    def _process_updates(self, data: Any) -> list[tuple[str, dict]]:
        return []

    def get_message_started(self) -> tuple[str, dict]:
        """返回 message_started 事件。"""
        return ("message_started", {})

    def get_completed_event(self) -> tuple[str, dict] | None:
        """从最终 State 生成 message_completed 事件。"""
        if self._final_state is None:
            return None
        fs = self._final_state
        conv = fs.get("conversation")
        return (
            "message_completed",
            {
                "conversation_id": conv.id if conv else "",
                "session_id": fs.get("session_id", ""),
                "trace_id": fs.get("trace_id", ""),
                "answer": fs.get("answer", ""),
            },
        )

    def get_failed_event(self, error_message: str) -> tuple[str, dict]:
        return ("message_failed", {"error_message": error_message})

    def get_closed_event(self) -> tuple[str, dict]:
        return ("stream_closed", {})

    def get_final_state(self) -> RuntimeGraphState | None:
        return self._final_state
