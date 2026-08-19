# 工具基类模块
#
# 定义 BaseTool 抽象基类，提供 async run() 模板方法。
# 所有 Tool 必须继承 BaseTool 并实现 async _execute() 方法，
# 框架自动处理：trace 埋点（复用全局 trace_id）、按工具类型分级超时、
# 异常捕获与包装、ToolResult 统一返回。
# _execute 支持两种返回格式：(data, evidence) 或 (data, evidence, metadata)。
#
# 超时语义（绝对 Deadline + 硬取消）：
#   - run() 用 asyncio.timeout 包住 _execute；到期时取消当前 Task。
#   - 实际预算 = min(工具默认超时, Deadline 剩余总预算)。
#   - Query 超时 → TOOL_TIMEOUT（可重试）；Write 超时 → WRITE_RESULT_UNKNOWN（不可重试）；
#     Analysis 默认按 LLM 预算。
#   - asyncio.CancelledError（用户主动取消）不吞掉，原样向上传播。

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from app.config.settings import settings
from app.core.logging.logger import get_logger
from app.core.timeout import child_timeout, current_deadline
from app.core.trace.trace_context import get_trace_id
from app.observability.langsmith_runs import arun_observed
from app.tool_center.contracts import BaseToolInput, Evidence, ToolError, ToolResult
from app.tool_center.exceptions import ToolException
from app.tool_center.telemetry import record_tool_trace
from app.utils.ids import new_trace_id as _gen_trace_id

logger = get_logger("ioc.tool_center")


def _deadline_expired() -> bool:
    """当前上下文的 Deadline 是否已过期（用于区分 Deadline 取消与用户取消）。"""
    current = current_deadline()
    return current is not None and current.expired

# _execute 方法的返回类型：
#   (data, evidence)                  — 二元组，兼容早期写法
#   (data, evidence, metadata)        — 三元组，metadata 供 Graph 判断空数据和来源
ToolExecutionResult = (
    tuple[dict[str, Any] | list | None, list[Evidence]]
    | tuple[dict[str, Any] | list | None, list[Evidence], dict[str, Any]]
)

# ToolType 枚举定义在 app/tool_registry/contracts.py，与 executor_catalog 同包；
# 为避免 tool_center ↔ tool_registry 循环导入，这里只使用其字符串值。
_QUERY = "query"
_ANALYSIS = "analysis"
_ACTION = "action"

# 单工具显式 timeout_seconds 的钳制范围（秒）。
# Query 工具允许在 10～15 秒之间配置；其余类型给出宽松上下界。
_TOOL_TYPE_RANGE: dict[str, tuple[float, float]] = {
    _QUERY: (10.0, 15.0),
    _ANALYSIS: (10.0, 60.0),
    _ACTION: (5.0, 60.0),
}


class BaseTool(ABC):
    """所有 Tool 的统一异步执行模板。

    子类只实现 async _execute；trace_id、分级超时、异常捕获、ToolResult 包装
    都在这里集中处理。Graph / Node 调用任何 Tool 时，按同一套
    success/error/evidence 协议处理。

    属性：
        tool_type: "query" / "analysis" / "action"（对应 ToolType 枚举值），决定默认超时与重试语义。
        timeout_seconds: 可选单工具超时覆盖（Query 钳制在 10～15 秒）。
    """

    name: str = ""
    description: str = ""
    tool_type: str = _QUERY
    timeout_seconds: float | None = None

    async def run(self, tool_input: BaseToolInput | None = None) -> ToolResult:
        safe_input = tool_input or BaseToolInput()
        input_summary = safe_input.model_dump()

        # 复用全局 trace_id（由 trace_middleware 在 HTTP 请求入口设置）；
        # 非 HTTP 上下文（如 LangGraph 内部调用）可能没有 trace_id，
        # 此时作为 fallback 生成一个，保持单向依赖 app/core。
        trace_id = get_trace_id() or safe_input.context.request_id
        if not trace_id:
            trace_id = _gen_trace_id()
            logger.debug("No global trace_id, generated fallback: %s", trace_id)

        start_time = time.perf_counter()
        timeout_seconds = self._default_timeout_seconds()
        budget = child_timeout(timeout_seconds)
        try:
            async with asyncio.timeout(budget):
                execution = await arun_observed(
                    self.name,
                    "tool",
                    self._execute(safe_input),
                    inputs=input_summary,
                    metadata={"tool_name": self.name, "tool_type": self.tool_type},
                    trace_id=trace_id,
                )
            data, evidence, metadata = self._unpack_execution_result(execution)
            duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            result = ToolResult(
                success=True,
                data=data,
                evidence=evidence,
                trace_id=trace_id,
                metadata=metadata,
            )
            record_tool_trace(
                trace_id=trace_id,
                tool_name=self.name,
                duration_ms=duration_ms,
                success=True,
                evidence_count=len(evidence),
                input_summary=input_summary,
                metadata=metadata,
            )
            return result
        except TimeoutError:
            duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            return self._timeout_result(
                trace_id=trace_id,
                tool_input=safe_input,
                timeout_seconds=budget,
                elapsed_ms=duration_ms,
                input_summary=input_summary,
            )
        except ToolException as e:
            duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            result = ToolResult(
                success=False,
                data=None,
                evidence=[],
                error=ToolError(
                    code=e.code,
                    message=e.message,
                    detail=e.detail,
                    retryable=e.retryable,
                ),
                trace_id=trace_id,
            )
            record_tool_trace(
                trace_id=trace_id,
                tool_name=self.name,
                duration_ms=duration_ms,
                success=False,
                error_code=e.code,
                input_summary=input_summary,
            )
            return result
        except asyncio.CancelledError:
            # 用户主动取消：不吞掉，原样向上传播。
            # 例外：如果外层 Deadline 恰好与本次执行同时到期（嵌套 asyncio.timeout
            # 竞态），此时 CancelledError 实为我们的 Deadline 取消，按超时结果返回，
            # 以便 Graph 收到结构化的 TOOL_TIMEOUT / WRITE_RESULT_UNKNOWN。
            if _deadline_expired():
                duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                return self._timeout_result(
                    trace_id=trace_id,
                    tool_input=safe_input,
                    timeout_seconds=budget,
                    elapsed_ms=duration_ms,
                    input_summary=input_summary,
                )
            raise
        except Exception as e:
            duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            wrapped = ToolException(code="TOOL_INTERNAL_ERROR", message=str(e), retryable=False)
            result = ToolResult(
                success=False,
                data=None,
                evidence=[],
                error=ToolError(
                    code=wrapped.code,
                    message=wrapped.message,
                    detail={"exception": str(e)},
                    retryable=False,
                ),
                trace_id=trace_id,
            )
            record_tool_trace(
                trace_id=trace_id,
                tool_name=self.name,
                duration_ms=duration_ms,
                success=False,
                error_code=wrapped.code,
                input_summary=input_summary,
            )
            return result

    def _timeout_result(
        self,
        *,
        trace_id: str,
        tool_input: BaseToolInput,
        timeout_seconds: float,
        elapsed_ms: int,
        input_summary: dict,
    ) -> ToolResult:
        """Deadline 超时结果：按工具类型区分 TOOL_TIMEOUT / WRITE_RESULT_UNKNOWN。"""
        detail: dict[str, Any] = {
            "timeout_seconds": timeout_seconds,
            "elapsed_ms": elapsed_ms,
            "tool_name": self.name,
            "tool_type": self.tool_type,
            "deadline_remaining_ms": max(0, int(timeout_seconds * 1000 - elapsed_ms)),
        }
        if self.tool_type == _ACTION:
            code = "WRITE_RESULT_UNKNOWN"
            message = "写操作超时，无法确认下游是否已提交，结果状态为 result_unknown"
            retryable = False
            detail["status"] = "result_unknown"
            detail["operation_id"] = getattr(tool_input, "operation_id", None) or f"op_{trace_id}"
            detail["idempotency_key"] = (
                getattr(tool_input, "idempotency_key", None) or f"idem_{trace_id}"
            )
        else:
            code = "TOOL_TIMEOUT"
            message = "工具执行超时"
            retryable = self.tool_type == _QUERY
        result = ToolResult(
            success=False,
            data=None,
            evidence=[],
            error=ToolError(
                code=code,
                message=message,
                detail=detail,
                retryable=retryable,
            ),
            trace_id=trace_id,
        )
        record_tool_trace(
            trace_id=trace_id,
            tool_name=self.name,
            duration_ms=elapsed_ms,
            success=False,
            error_code=code,
            input_summary=input_summary,
            metadata={"timeout_seconds": timeout_seconds},
        )
        return result

    def _default_timeout_seconds(self) -> float:
        """工具类型 → 默认超时（秒）。Analysis 按 LLM 预算，因为其子调用可能含 LLM。"""
        if self.tool_type == _ACTION:
            return settings.tool_write_timeout_seconds
        if self.tool_type == _ANALYSIS:
            return settings.llm_timeout_seconds
        return settings.tool_query_timeout_seconds

    def effective_timeout_seconds(self) -> float:
        """实际生效的超时（秒）：显式 timeout_seconds 优先，并按类型钳制。"""
        explicit = self.timeout_seconds
        if explicit is None:
            return self._default_timeout_seconds()
        low, high = _TOOL_TYPE_RANGE.get(self.tool_type, (1.0, max(explicit, 1.0)))
        return min(max(explicit, low), high)

    @abstractmethod
    async def _execute(self, tool_input: BaseToolInput) -> ToolExecutionResult:
        """Tool 的业务执行点（异步）。

        Query Tool 在这里调用 Client（异步），不直接查库、不调用 LLM、不写 Prompt。
        必须协作取消：底层 await 应能在 CancelledError 时及时退出并释放资源。
        """

        pass

    def _unpack_execution_result(
        self,
        result: ToolExecutionResult,
    ) -> tuple[dict[str, Any] | list | None, list[Evidence], dict[str, Any]]:
        # 兼容早期二元返回，新的 Tool 可以返回 metadata 方便 Graph 判断空数据和来源。
        if len(result) == 2:
            data, evidence = result
            return data, evidence, {}
        data, evidence, metadata = result
        return data, evidence, metadata
