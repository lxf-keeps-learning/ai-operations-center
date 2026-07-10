"""
Trace 上下文 — 通过 ContextVar 在异步请求范围内安全传递 traceId

traceId 贯穿一次请求的全链路：
  Browser → API → Service → Graph → Tool → LLM → Response

使用 ContextVar 而非全局变量，确保异步框架下各请求的 traceId 互相隔离。
"""

from contextvars import ContextVar

# ContextVar 提供异步任务级别的变量隔离
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def set_trace_id(trace_id: str) -> None:
    """设置当前请求的 traceId（通常在中间件中调用）"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """获取当前请求的 traceId，未设置时返回空字符串"""
    return _trace_id_var.get()


def clear_trace_id() -> None:
    """清理当前请求的 traceId（请求结束时调用）"""
    _trace_id_var.set("")
