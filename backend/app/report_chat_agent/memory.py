"""Report Chat 的分层长期记忆与 LangGraph 官方 Store 节点。"""

from datetime import UTC, datetime
import hashlib
from typing import Any, Literal

from langgraph.runtime import Runtime

from app.report_chat_agent.state import ReportChatState
from app.security.content_moderator import ModerationAction, content_moderator

USER_MEMORY_NAMESPACE = "user_memory"
REPORT_MEMORY_NAMESPACE = "report_memory"
MAX_CHAT_HISTORY = 12
MemoryScope = Literal["user", "report"]


def _context_value(runtime: Runtime[Any], key: str, fallback: str = "") -> str:
    context = runtime.context or {}
    if isinstance(context, dict):
        return str(context.get(key) or fallback)
    return fallback


def _user_id(state: ReportChatState, runtime: Runtime[Any]) -> str:
    return state.get("user_id") or _context_value(runtime, "user_id", "anonymous")


def _namespace(
    state: ReportChatState,
    runtime: Runtime[Any],
    scope: MemoryScope,
) -> tuple[str, ...]:
    user_id = _user_id(state, runtime)
    if scope == "user":
        return (user_id, USER_MEMORY_NAMESPACE)
    return (user_id, REPORT_MEMORY_NAMESPACE, str(state.get("report_id", "")))


def _memory_scope(question: str) -> tuple[MemoryScope, str]:
    """根据用户明确表达决定记忆归属，默认将报告追问归入报告记忆。"""
    if any(marker in question for marker in ("我的偏好", "我喜欢", "我习惯", "以后")):
        return "user", "user_preference"
    return "report", "report_fact"


def _memory_content(question: str) -> str:
    for marker in ("我的偏好是", "我喜欢", "我习惯", "请记住", "记住"):
        if marker in question:
            return question.split(marker, 1)[1].strip(" ：:，,。")
    return question.strip()


def _memory_key(scope: MemoryScope, content: str, report_id: str) -> str:
    scope_key = f"{scope}:{report_id if scope == 'report' else ''}:{content}"
    digest = hashlib.sha256(scope_key.encode("utf-8")).hexdigest()[:24]
    return f"memory-{digest}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load_chat_memory_node(
    state: ReportChatState,
    runtime: Runtime[Any],
) -> ReportChatState:
    """恢复当前会话历史，并分别检索用户级和当前报告级记忆。"""
    history = list(state.get("chat_history") or [])[-MAX_CHAT_HISTORY:]
    memories: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = list(state.get("errors") or [])
    if runtime.store is not None:
        query = state.get("user_question", "").strip()
        namespaces = [_namespace(state, runtime, "user")]
        if state.get("report_id"):
            namespaces.append(_namespace(state, runtime, "report"))
        for namespace in namespaces:
            try:
                items = runtime.store.search(namespace, query=query, limit=5)
                memories.extend(
                    {
                        "key": item.key,
                        "value": item.value,
                        "namespace": list(item.namespace),
                        "scope": "report" if item.namespace[1] == REPORT_MEMORY_NAMESPACE else "user",
                    }
                    for item in items
                )
            except Exception as exc:
                errors.append({"node": "load_chat_memory", "message": str(exc)})
    return {"chat_history": history, "memory_context": memories[:5], "errors": errors}


def save_chat_memory_node(
    state: ReportChatState,
    runtime: Runtime[Any],
) -> ReportChatState:
    """保存会话状态，并将用户明确要求记住的内容结构化写入 Store。"""
    history = list(state.get("chat_history") or [])
    question = state.get("user_question", "").strip()
    answer = state.get("final_answer", "").strip()
    if question and answer:
        history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])

    memory_saved = False
    marker_present = any(marker in question for marker in ("请记住", "记住", "以后都", "我的偏好是"))
    user_id = _user_id(state, runtime)
    if marker_present and runtime.store is not None and user_id != "anonymous":
        content = _memory_content(question)
        moderation = content_moderator.moderate(content)
        if content and moderation.action != ModerationAction.BLOCK:
            scope, memory_type = _memory_scope(question)
            report_id = str(state.get("report_id", ""))
            now = _now()
            value = {
                "memory_type": memory_type,
                "scope": scope,
                "content": moderation.masked_text or content,
                "report_id": report_id if scope == "report" else None,
                "source": {
                    "trace_id": state.get("trace_id", ""),
                    "session_id": state.get("session_id", ""),
                    "runtime_session_id": state.get("runtime_session_id", ""),
                    "source_type": "explicit_user_memory",
                },
                "confidence": 1.0,
                "importance": 0.8,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            try:
                runtime.store.put(
                    _namespace(state, runtime, scope),
                    _memory_key(scope, content, report_id),
                    value,
                )
                memory_saved = True
            except Exception as exc:
                errors = list(state.get("errors") or [])
                errors.append({"node": "save_chat_memory", "message": str(exc)})
                return {
                    "chat_history": history[-MAX_CHAT_HISTORY:],
                    "memory_saved": False,
                    "errors": errors,
                }

    return {
        "chat_history": history[-MAX_CHAT_HISTORY:],
        "memory_saved": memory_saved,
    }
