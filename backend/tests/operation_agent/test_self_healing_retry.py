"""Operation 自修复重试策略测试（Tool 与 LLM）。"""

import pytest

from app.operation_agent.self_healing.events import record_operation_attempts
from app.operation_agent.self_healing.retry_llm import should_retry_llm_result
from app.operation_agent.self_healing.retry_ops import (
    operation_retry_policy,
    run_tool_with_retry,
)
from app.operation_agent.self_healing.retry_tool import (
    RETRYABLE_TOOL_CAPABILITIES,
    get_tool_retry_delay_seconds,
    should_retry_tool_result,
    tool_is_retryable,
)
from app.runtime.llm.client import LlmResult
from app.tool_center.contracts import ToolContext, ToolError, ToolResult


def _tool_result(success: bool, code: str, *, retryable: bool = False, detail: dict | None = None) -> ToolResult:
    return ToolResult(
        success=success,
        data=None if success else None,
        evidence=[],
        error=None if success else ToolError(code=code, message=code, detail=detail, retryable=retryable),
    )


class TestToolRetryPolicy:
    def test_only_query_analysis_tools_are_retryable(self):
        assert "query.kpi" in RETRYABLE_TOOL_CAPABILITIES
        assert "analysis.ioc_summary" in RETRYABLE_TOOL_CAPABILITIES
        assert tool_is_retryable("action.work_order.draft") is False

    def test_success_is_not_retried(self):
        result = _tool_result(True, "")
        assert should_retry_tool_result(result, "query.kpi") is False

    def test_retryable_error_is_retried(self):
        result = _tool_result(False, "TOOL_TIMEOUT", retryable=True)
        assert should_retry_tool_result(result, "query.kpi") is True

    def test_non_retryable_error_is_not_retried(self):
        result = _tool_result(False, "TOOL_TIMEOUT", retryable=False)
        assert should_retry_tool_result(result, "query.kpi") is False

    def test_action_tool_never_retries(self):
        result = _tool_result(False, "TOOL_TIMEOUT", retryable=True)
        assert should_retry_tool_result(result, "action.work_order.draft") is False

    def test_write_result_unknown_never_retries(self):
        result = _tool_result(False, "WRITE_RESULT_UNKNOWN", retryable=True)
        assert should_retry_tool_result(result, "query.kpi") is False

    def test_param_permission_confirmation_content_safety_never_retry(self):
        for code in (
            "TOOL_VALIDATION_ERROR",
            "TOOL_FORBIDDEN",
            "TOOL_CONFIRMATION_REQUIRED",
            "CONTENT_SAFETY_BLOCKED",
            "TOOL_CAPABILITY_UNAVAILABLE",
            "TOOL_NOT_FOUND",
            "TOOL_REGISTRY_CONFIGURATION_ERROR",
        ):
            result = _tool_result(False, code, retryable=True)
            assert should_retry_tool_result(result, "query.kpi") is False, code

    def test_rate_limited_retries_only_when_retry_after_within_two_seconds(self):
        quick = _tool_result(False, "TOOL_RATE_LIMITED", retryable=True, detail={"retry_after_seconds": 1})
        assert should_retry_tool_result(quick, "query.kpi") is True

        slow = _tool_result(False, "TOOL_RATE_LIMITED", retryable=True, detail={"retry_after_seconds": 30})
        assert should_retry_tool_result(slow, "query.kpi") is False

        unknown = _tool_result(False, "TOOL_RATE_LIMITED", retryable=True, detail=None)
        assert should_retry_tool_result(unknown, "query.kpi") is False

    def test_rate_limit_delay_uses_retry_after(self):
        result = _tool_result(
            False,
            "TOOL_RATE_LIMITED",
            retryable=True,
            detail={"retry_after_seconds": 1.5},
        )
        assert get_tool_retry_delay_seconds(result) == pytest.approx(1.5)


def _llm_result(success: bool, error_code: str = "") -> LlmResult:
    return LlmResult(
        content="" if not success else "ok",
        model="deepseek-chat",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_ms=1,
        success=success,
        error_message="" if success else "err",
        error_code=error_code,
    )


class TestLlmRetryPolicy:
    def test_timeout_is_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_TIMEOUT")) is True

    def test_network_error_is_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_NETWORK_ERROR")) is True

    def test_rate_limited_is_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_RATE_LIMITED")) is True

    def test_provider_5xx_is_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_PROVIDER_ERROR")) is True

    def test_auth_error_not_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_AUTH_ERROR")) is False

    def test_invalid_request_not_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_INVALID_REQUEST")) is False

    def test_content_policy_not_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "LLM_CONTENT_POLICY")) is False

    def test_user_cancel_not_retryable(self):
        assert should_retry_llm_result(_llm_result(False, "CANCELLED_BY_USER")) is False

    def test_success_not_retried(self):
        assert should_retry_llm_result(_llm_result(True)) is False


@pytest.mark.anyio
async def test_operation_retry_policy_maps_settings(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "operation_retry_max_attempts", 3)
    monkeypatch.setattr(settings, "operation_retry_initial_backoff_seconds", 1.0)
    monkeypatch.setattr(settings, "operation_retry_max_backoff_seconds", 4.0)

    policy = operation_retry_policy()
    assert policy.max_attempts == 3
    assert policy.initial_backoff_seconds == 1.0
    assert policy.max_backoff_seconds == 4.0


def test_operation_attempt_stats_count_first_attempt_without_marking_it_retried():
    state = {}

    record_operation_attempts(
        state,
        "llm:analyze_reason",
        attempts=1,
        exhausted=False,
    )

    assert state["self_healing"]["total_attempts"] == 1
    assert state["self_healing"]["retried_operations"] == []


def test_operation_attempt_stats_record_actual_retry():
    state = {}

    record_operation_attempts(
        state,
        "tool:query.kpi",
        attempts=2,
        exhausted=False,
        error_code="TOOL_TIMEOUT",
    )

    assert state["self_healing"]["total_attempts"] == 2
    assert state["self_healing"]["retried_operations"] == [{
        "operation": "tool:query.kpi",
        "attempts": 2,
        "exhausted": False,
        "error_code": "TOOL_TIMEOUT",
    }]


@pytest.mark.anyio
async def test_tool_attempt_returning_none_does_not_crash_retry_wrapper():
    state = {}

    async def missing_result():
        return None

    result = await run_tool_with_retry(
        state,
        "query.kpi",
        {},
        ToolContext(),
        attempt=missing_result,
    )

    assert result is None
    assert state["self_healing"]["total_attempts"] == 1
