"""Operation 专用重试执行器：Tool / LLM 的异步重试 + 状态事件记录。

复用一个职责单一的异步重试核心（app.core.retry.run_with_retry），
并为 Operation Graph 节点补足：
  - 每次尝试分别写入 llm_usages（重试 Token 与延迟不丢失）；
  - 重试事件写入 recovery_events 与日志；
  - 重试统计登记到 self_healing.retried_operations / total_attempts。
"""

from __future__ import annotations

from typing import Any, Callable

from app.config.settings import settings
from app.core.retry import RetryPolicy, RetryOutcome, run_with_retry
from app.core.timeout import current_deadline
from app.operation_agent.self_healing.events import (
    emit_recovery_event,
    record_operation_attempts,
)
from app.operation_agent.self_healing.retry_llm import should_retry_llm_result
from app.operation_agent.self_healing.retry_tool import (
    get_tool_retry_delay_seconds,
    should_retry_tool_result,
)
from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client
from app.tool_center.contracts import ToolContext, ToolResult
from app.tool_registry.compat import aexecute_tool


def operation_retry_policy() -> RetryPolicy:
    """从 Settings 构建 Operation 重试策略。"""
    return RetryPolicy(
        max_attempts=settings.operation_retry_max_attempts,
        initial_backoff_seconds=settings.operation_retry_initial_backoff_seconds,
        max_backoff_seconds=settings.operation_retry_max_backoff_seconds,
        min_recovery_budget_seconds=settings.operation_min_recovery_budget_seconds,
    )


def _state_event_hook(state: OperationState, node: str) -> Callable[[str, dict[str, Any]], None]:
    def hook(event_type: str, fields: dict[str, Any]) -> None:
        emit_recovery_event(
            state,
            event_type,
            node=node,
            operation=fields.get("operation"),
            attempt=fields.get("attempt"),
        )

    return hook


async def run_tool_with_retry(
    state: OperationState,
    capability: str,
    filters: dict[str, Any],
    context: ToolContext,
    *,
    node: str = "query_operation_data",
    attempt: Callable[[], Any] | None = None,
) -> ToolResult | None:
    """执行一次 Tool 调用并应用 Operation 重试策略。

    只重试失败的 Tool；成功的 Tool 不会因其他 Tool 失败而重复调用。
    返回最后一次 ToolResult（失败时调用方负责写 error 记录）。
    可通过 attempt 注入单次执行函数（便于测试拦截与取消传播）。
    """
    policy = operation_retry_policy()
    holder: dict[str, Any] = {}

    async def default_attempt() -> ToolResult:
        return await aexecute_tool(capability, filters, context)

    single_attempt = attempt or default_attempt

    async def wrapped_attempt() -> ToolResult:
        result = await single_attempt()
        holder["last"] = result
        return result

    outcome: RetryOutcome[ToolResult] = await run_with_retry(
        wrapped_attempt,
        should_retry=lambda result: should_retry_tool_result(result, capability),
        is_success=lambda result: result is not None and result.success,
        policy=policy,
        deadline=current_deadline(),
        on_event=_state_event_hook(state, node),
        operation=f"tool:{capability}",
        retry_delay_seconds=get_tool_retry_delay_seconds,
    )

    result: ToolResult | None = holder.get("last")
    error_code = result.error.code if result and result.error else None
    record_operation_attempts(
        state,
        f"tool:{capability}",
        attempts=outcome.attempts,
        exhausted=outcome.exhausted,
        error_code=error_code,
    )
    return result


async def achat_operation_llm(
    *,
    state: OperationState,
    prompt_content: str | None,
    user_message: str,
    action_type: str,
    timeout_seconds: float,
    node: str,
    prompt_key: str | None = None,
    prompt_version: str | None = None,
    prompt_commit_hash: str | None = None,
) -> LlmResult:
    """调用 LLM 并应用 Operation 重试策略；每次尝试写入 llm_usages。"""
    policy = operation_retry_policy()
    holder: dict[str, Any] = {}

    async def attempt() -> LlmResult:
        result = await llm_client.achat(
            prompt_content=prompt_content,
            user_message=user_message,
            timeout_seconds=timeout_seconds,
        )
        holder["last"] = result
        _record_llm_usage(
            state,
            result,
            action_type=action_type,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            prompt_commit_hash=prompt_commit_hash,
        )
        return result

    outcome: RetryOutcome[LlmResult] = await run_with_retry(
        attempt,
        should_retry=should_retry_llm_result,
        is_success=lambda result: result.success,
        policy=policy,
        deadline=current_deadline(),
        on_event=_state_event_hook(state, node),
        operation=f"llm:{action_type}",
    )

    result = holder.get("last")
    record_operation_attempts(
        state,
        f"llm:{action_type}",
        attempts=outcome.attempts,
        exhausted=outcome.exhausted,
        error_code=(result.error_code if result else None) or "",
    )
    return result


def _record_llm_usage(
    state: OperationState,
    result: LlmResult,
    *,
    action_type: str,
    prompt_key: str | None = None,
    prompt_version: str | None = None,
    prompt_commit_hash: str | None = None,
) -> None:
    usages = state.setdefault("llm_usages", [])
    usages.append({
        "action_type": action_type,
        "model_name": result.model,
        "input_tokens": result.prompt_tokens,
        "output_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "success": 1 if result.success else 0,
        "error_message": result.error_message if not result.success else None,
        "error_code": result.error_code or None,
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "prompt_commit_hash": prompt_commit_hash,
    })
