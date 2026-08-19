"""Tool 分级超时与硬取消专项测试。

验证：
  1. Query Tool 超时 → TOOL_TIMEOUT，底层协程收到取消，副作用不再继续。
  2. Write Tool 超时 → WRITE_RESULT_UNKNOWN，不标记可重试。
  3. Analysis Tool 默认预算来自 LLM 60s 配置。
  4. 总预算传播：报告只剩 3 秒时 Query Tool 不能获得完整 15 秒。
  5. 用户主动取消（CancelledError）与 Deadline 超时（TimeoutError）区分，不吞取消。
"""

import asyncio
import time

import pytest

from app.config.settings import settings
from app.core.timeout import deadline
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, Evidence
from app.tool_center.exceptions import ToolTimeoutError
from app.tool_registry.contracts import ToolType


class _SlowQueryTool(BaseTool):
    """Async 查询工具：睡眠超过预算，并在取消时记录 CancelledError。"""

    name = "test_slow_query"
    description = "slow query"
    tool_type = ToolType.QUERY
    cancelled_by_user = False
    cancelled_by_deadline = False
    side_effect_after_timeout = 0

    async def _execute(self, tool_input: BaseToolInput):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            _SlowQueryTool.cancelled_by_user = True
            raise
        _SlowQueryTool.side_effect_after_timeout += 1
        return {"ok": True}, []


class _SlowWriteTool(BaseTool):
    name = "test_slow_write"
    description = "slow write"
    tool_type = ToolType.ACTION
    cancelled = False

    async def _execute(self, tool_input: BaseToolInput):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            _SlowWriteTool.cancelled = True
            raise
        return {"committed": True}, []


class _FastQueryTool(BaseTool):
    name = "test_fast_query"
    description = "fast query"
    tool_type = ToolType.QUERY

    async def _execute(self, tool_input: BaseToolInput):
        return {"items": []}, [Evidence(source="t", source_type="t")]


class _QueryToolRecordingBudget(BaseTool):
    """记录实际生效的 asyncio.timeout 预算（通过剩余可用时间推算）。"""

    name = "test_budget_query"
    description = "budget query"
    tool_type = ToolType.QUERY
    observed_budget: float | None = None

    async def _execute(self, tool_input: BaseToolInput):
        start = time.monotonic()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            _QueryToolRecordingBudget.observed_budget = time.monotonic() - start
            raise
        return {"items": []}, []


class TestToolTimeout:
    @pytest.fixture(autouse=True)
    def _short_timeouts(self, monkeypatch):
        monkeypatch.setattr(settings, "tool_query_timeout_seconds", 0.1)
        monkeypatch.setattr(settings, "tool_write_timeout_seconds", 0.1)
        monkeypatch.setattr(settings, "llm_timeout_seconds", 0.1)

    @pytest.mark.anyio
    async def test_query_timeout_returns_tool_timeout(self) -> None:
        _SlowQueryTool.cancelled_by_user = False
        result = await _SlowQueryTool().run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "TOOL_TIMEOUT"
        assert result.error.retryable is True  # 安全查询可重试
        assert result.error.detail["timeout_seconds"] == pytest.approx(0.1, abs=0.05)
        assert result.error.detail["elapsed_ms"] > 0
        assert result.error.detail["deadline_remaining_ms"] >= 0

    @pytest.mark.anyio
    async def test_query_timeout_underlying_coroutine_cancelled(self) -> None:
        _SlowQueryTool.cancelled_by_user = False
        _SlowQueryTool.side_effect_after_timeout = 0
        result = await _SlowQueryTool().run(BaseToolInput())
        assert result.success is False
        # 底层协程确实被取消（在 sleep 里收到 CancelledError）
        assert _SlowQueryTool.cancelled_by_user is True
        # 取消后不再继续执行副作用
        assert _SlowQueryTool.side_effect_after_timeout == 0

    @pytest.mark.anyio
    async def test_write_timeout_is_result_unknown_not_retryable(self) -> None:
        _SlowWriteTool.cancelled = False
        result = await _SlowWriteTool().run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "WRITE_RESULT_UNKNOWN"
        assert result.error.retryable is False  # result_unknown 不得自动重试
        assert result.error.detail["status"] == "result_unknown"
        assert result.error.detail["operation_id"]
        assert result.error.detail["idempotency_key"]
        assert _SlowWriteTool.cancelled is True

    @pytest.mark.anyio
    async def test_fast_query_no_timeout(self) -> None:
        result = await _FastQueryTool().run(BaseToolInput())
        assert result.success is True

    @pytest.mark.anyio
    async def test_analysis_default_budget_uses_llm_timeout(self) -> None:
        class _AnalysisTool(BaseTool):
            name = "test_analysis"
            description = "analysis"
            tool_type = ToolType.ANALYSIS

            async def _execute(self, tool_input: BaseToolInput):
                return {}, []

        tool = _AnalysisTool()
        assert tool.effective_timeout_seconds() == pytest.approx(
            settings.llm_timeout_seconds
        )

    @pytest.mark.anyio
    async def test_query_timeout_does_not_swallow_user_cancel(self) -> None:
        """用户主动取消（CancelledError）必须继续向上传播，不能被包装成 ToolResult。"""
        tool = _SlowQueryTool()
        _SlowQueryTool.cancelled_by_user = False
        task = asyncio.create_task(tool.run(BaseToolInput()))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert _SlowQueryTool.cancelled_by_user is True


class TestBudgetPropagation:
    @pytest.mark.anyio
    async def test_query_tool_respects_remaining_report_budget(self) -> None:
        """报告只剩 3 秒时，Query Tool 只能拿到 ≤3 秒预算而不是完整 15 秒。"""
        _QueryToolRecordingBudget.observed_budget = None
        async with deadline(0.3, operation="report"):
            result = await _QueryToolRecordingBudget().run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "TOOL_TIMEOUT"
        assert _QueryToolRecordingBudget.observed_budget is not None
        assert _QueryToolRecordingBudget.observed_budget < 1.0
        assert _QueryToolRecordingBudget.observed_budget <= 0.5


class TestTimeoutErrorMapping:
    def test_tool_timeout_error_retryable_flag(self) -> None:
        err = ToolTimeoutError("timeout")
        assert err.code == "TOOL_TIMEOUT"
        assert err.retryable is True
