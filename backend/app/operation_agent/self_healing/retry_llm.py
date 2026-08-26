"""LLM 调用重试策略（Operation Agent 专用）。"""

from __future__ import annotations

from app.runtime.llm.client import LlmResult, RETRYABLE_LLM_ERROR_CODES


def should_retry_llm_result(result: LlmResult) -> bool:
    """单次 LlmResult 是否可重试。

    允许：LLM_TIMEOUT / 网络连接异常 / Provider 限流(429) / Provider 5xx。
    禁止：API Key 或 Provider 配置错误、普通 4xx 参数错误、内容安全拦截、
    用户主动取消、Deadline 已耗尽（后者由重试模块的预算保护拦截）。
    """
    if result.success:
        return False
    code = result.error_code or ""
    if code == "CANCELLED_BY_USER":
        return False
    return code in RETRYABLE_LLM_ERROR_CODES
