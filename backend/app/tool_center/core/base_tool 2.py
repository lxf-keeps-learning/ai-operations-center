from abc import ABC, abstractmethod
from typing import Any

from app.tool_center.core.exceptions import ToolException
from app.tool_center.core.schemas import BaseToolInput, Evidence, ToolError, ToolResult
from app.tool_center.core.trace import end_trace, start_trace

ToolExecutionResult = (
    tuple[dict[str, Any] | list | None, list[Evidence]]
    | tuple[dict[str, Any] | list | None, list[Evidence], dict[str, Any]]
)


class BaseTool(ABC):
    """所有 Tool 的统一执行模板。

    子类只实现 _execute；trace_id、异常捕获、ToolResult 包装都在这里集中处理。
    这样 Graph / Node 调用任何 Tool 时，都能按同一套 success/error/evidence 协议处理。
    """

    name: str = ""
    description: str = ""

    def run(self, tool_input: BaseToolInput | None = None) -> ToolResult:
        safe_input = tool_input or BaseToolInput()
        input_summary = safe_input.model_dump()
        trace_id, start_time = start_trace(self.name, input_summary)
        try:
            data, evidence, metadata = self._unpack_execution_result(self._execute(safe_input))
            result = ToolResult(
                success=True,
                data=data,
                evidence=evidence,
                trace_id=trace_id,
                metadata=metadata,
            )
            end_trace(
                trace_id=trace_id,
                tool_name=self.name,
                start_time=start_time,
                success=True,
                evidence_count=len(evidence),
                input_summary=input_summary,
                metadata=metadata,
            )
            return result
        except ToolException as e:
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
            end_trace(
                trace_id=trace_id,
                tool_name=self.name,
                start_time=start_time,
                success=False,
                error_code=e.code,
                input_summary=input_summary,
            )
            return result
        except Exception as e:
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
            end_trace(
                trace_id=trace_id,
                tool_name=self.name,
                start_time=start_time,
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
