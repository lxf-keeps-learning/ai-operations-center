from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolException
from app.tool_center.contracts import BaseToolInput, Evidence


class SuccessTool(BaseTool):
    name = "test_success_tool"
    description = "A tool that always succeeds"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list[Evidence]]:
        data = [{"id": 1, "value": "ok"}]
        evidence = [
            Evidence(
                source="test",
                source_type="mock",
                record_id="rec_001",
                description="test evidence",
            )
        ]
        return data, evidence


class ErrorTool(BaseTool):
    name = "test_error_tool"
    description = "A tool that always raises ToolException"

    def _execute(self, tool_input: BaseToolInput) -> tuple[None, list]:
        raise ToolException(code="TOOL_CUSTOM_ERROR", message="something went wrong", retryable=True)


class CrashTool(BaseTool):
    name = "test_crash_tool"
    description = "A tool that crashes with unexpected exception"

    def _execute(self, tool_input: BaseToolInput) -> tuple[None, list]:
        raise ValueError("unexpected crash")


class EmptyDataTool(BaseTool):
    name = "test_empty_tool"
    description = "A tool that returns empty data"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list]:
        return [], []


class MetadataTool(BaseTool):
    name = "test_metadata_tool"
    description = "A tool that returns metadata"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list, dict]:
        return [], [], {"empty": True, "source": "unit_test"}


class TestBaseTool:
    def test_success_returns_success_true(self):
        tool = SuccessTool()
        result = tool.run(BaseToolInput())
        assert result.success is True
        assert result.data == [{"id": 1, "value": "ok"}]
        assert len(result.evidence) == 1
        assert result.error is None

    def test_success_contains_trace_id(self):
        tool = SuccessTool()
        result = tool.run(BaseToolInput())
        assert result.trace_id is not None
        assert result.trace_id.startswith("trace_")

    def test_tool_exception_returns_success_false(self):
        tool = ErrorTool()
        result = tool.run(BaseToolInput())
        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.code == "TOOL_CUSTOM_ERROR"
        assert result.error.retryable is True

    def test_tool_exception_contains_trace_id(self):
        tool = ErrorTool()
        result = tool.run(BaseToolInput())
        assert result.trace_id is not None

    def test_unexpected_exception_returns_internal_error(self):
        tool = CrashTool()
        result = tool.run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "TOOL_INTERNAL_ERROR"
        assert result.error.retryable is False

    def test_unexpected_exception_contains_trace_id(self):
        tool = CrashTool()
        result = tool.run(BaseToolInput())
        assert result.trace_id is not None

    def test_empty_data_returns_success_with_empty_list(self):
        tool = EmptyDataTool()
        result = tool.run(BaseToolInput())
        assert result.success is True
        assert result.data == []
        assert result.error is None

    def test_context_is_optional(self):
        tool = SuccessTool()
        result = tool.run(BaseToolInput())
        assert result.success is True

    def test_run_accepts_default_input(self):
        tool = SuccessTool()
        result = tool.run()
        assert result.success is True

    def test_success_can_return_metadata(self):
        tool = MetadataTool()
        result = tool.run(BaseToolInput())
        assert result.success is True
        assert result.metadata["empty"] is True
        assert result.metadata["source"] == "unit_test"
