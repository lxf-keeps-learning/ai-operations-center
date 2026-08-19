"""超时与取消基础设施。

提供基于单调时钟的绝对 Deadline，通过 contextvars 在请求 → Graph → Node →
Tool → LLM 之间传播预算；子层只能取 min(自身默认, 剩余总预算)，不允许每层
重新获得完整预算。
"""

from app.core.timeout.deadline import (
    Deadline,
    child_timeout,
    current_deadline,
    deadline,
)
from app.core.timeout.errors import (
    DeadlineExpiredError,
    ReportTimeoutError,
    SseIdleTimeoutError,
)

__all__ = [
    "Deadline",
    "DeadlineExpiredError",
    "ReportTimeoutError",
    "SseIdleTimeoutError",
    "child_timeout",
    "current_deadline",
    "deadline",
]
