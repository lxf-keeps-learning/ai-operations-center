"""
LLM 流式回调上下文 — 使用 ContextVar 跨线程传递 streaming callback。

在 chat_stream 场景中，Graph 在后台线程（asyncio.to_thread）中执行，
LLM 节点通过此模块检测当前请求是否期望流式输出，若是则将 chunk 实时回传。

设计模式与 report_chat_agent/stream_context.py 一致。
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar

# LLM 流式回调类型：接收一个文本片段，无返回值
LlmStreamCallback = Callable[[str], None]

# ContextVar 默认值为 None，表示非流式模式
_llm_stream_callback: ContextVar[LlmStreamCallback | None] = ContextVar(
    "runtime_llm_stream_callback",
    default=None,
)


def get_llm_stream_callback() -> LlmStreamCallback | None:
    """获取当前请求的流式回调，None 表示使用同步 chat()"""
    return _llm_stream_callback.get()


@contextmanager
def use_llm_stream_callback(callback: LlmStreamCallback) -> Generator[None, None, None]:
    """在 with 块内注册流式回调，块结束后自动恢复 ContextVar"""
    token = _llm_stream_callback.set(callback)
    try:
        yield
    finally:
        _llm_stream_callback.reset(token)
