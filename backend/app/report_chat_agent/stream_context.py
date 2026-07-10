"""Report Chat 回答流上下文。

使用 ContextVar 将本次请求的 chunk 回调传给 Graph 内部回答节点，避免把
不可序列化的回调函数放入 ReportChatState。asyncio.to_thread 会复制当前
context，因此 Graph 即使在线程中执行也能读取本请求回调。
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar

AnswerStreamCallback = Callable[[str], None]

_answer_stream_callback: ContextVar[AnswerStreamCallback | None] = ContextVar(
    "report_chat_answer_stream_callback",
    default=None,
)


def get_answer_stream_callback() -> AnswerStreamCallback | None:
    return _answer_stream_callback.get()


@contextmanager
def use_answer_stream_callback(
    callback: AnswerStreamCallback,
) -> Generator[None, None, None]:
    token = _answer_stream_callback.set(callback)
    try:
        yield
    finally:
        _answer_stream_callback.reset(token)
