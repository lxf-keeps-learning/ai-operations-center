# 工具基类模块
#
# 定义 BaseTool 抽象基类，提供 run() 模板方法。
# 所有 Tool 必须继承 BaseTool 并实现 _execute() 方法，
# 框架自动处理：trace 埋点（复用全局 trace_id）、异常捕获与包装、ToolResult 统一返回。
# _execute 支持两种返回格式：(data, evidence) 或 (data, evidence, metadata)。

import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging.logger import get_logger
from app.core.trace.trace_context import get_trace_id
from app.tool_center.contracts import BaseToolInput, Evidence, ToolError, ToolResult
from app.tool_center.exceptions import ToolException
from app.tool_center.telemetry import record_tool_trace
from app.utils.ids import new_trace_id as _gen_trace_id

logger = get_logger("ioc.tool_center")

# _execute 方法的返回类型：
#   (data, evidence)                  — 二元组，兼容早期写法
#   (data, evidence, metadata)        — 三元组，metadata 供 Graph 判断空数据和来源
ToolExecutionResult = (
    tuple[dict[str, Any] | list | None, list[Evidence]]
    | tuple[dict[str, Any] | list | None, list[Evidence], dict[str, Any]]
)


class BaseTool(ABC):
    """所有 Tool 的统一执行模板。

    子类只实现 _execute；trace_id、异常捕获、ToolResult 包装都在这里集中处理。
    这样 Graph / Node 调用任何 Tool 时，都能按同一套 success/error/evidence 协议处理。
    trace_id 复用全局请求链路（来自 app/core/trace），确保全链路 trace_id 一致；
    如需 Tool 调用级别细分，可在 future 使用 tool_call_id 或 span_id。
    """

    name: str = ""
    description: str = ""

    def run(self, tool_input: BaseToolInput | None = None) -> ToolResult:
        safe_input = tool_input or BaseToolInput()
        input_summary = safe_input.model_dump()

        # 复用全局 trace_id（由 trace_middleware 在 HTTP 请求入口设置）；
        # 非 HTTP 上下文（如 LangGraph 内部调用）可能没有 trace_id，
        # 此时作为 fallback 生成一个，保持单向依赖 app/core。
        trace_id = get_trace_id()
        if not trace_id:
            trace_id = _gen_trace_id()
            logger.debug("No global trace_id, generated fallback: %s", trace_id)

        start_time = time.perf_counter()
        try:
            data, evidence, metadata = self._unpack_execution_result(self._execute(safe_input))
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

    @abstractmethod
    def _execute(self, tool_input: BaseToolInput) -> ToolExecutionResult:
        """Tool 的业务执行点。

        Query Tool 在这里调用 Client，不直接查库、不调用 LLM、不写 Prompt。
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
