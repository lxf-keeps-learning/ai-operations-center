import pytest
from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolException
from app.tool_center.contracts import BaseToolInput, Evidence


class SuccessTool(BaseTool):
    name = "test_success_tool"
    description = "A tool that always succeeds"

    async def _execute(self, tool_input: BaseToolInput) -> tuple[list, list[Evidence]]:
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

    async def _execute(self, tool_input: BaseToolInput) -> tuple[None, list]:
        raise ToolException(code="TOOL_CUSTOM_ERROR", message="something went wrong", retryable=True)


class CrashTool(BaseTool):
    name = "test_crash_tool"
    description = "A tool that crashes with unexpected exception"

    async def _execute(self, tool_input: BaseToolInput) -> tuple[None, list]:
        raise ValueError("unexpected crash")


class EmptyDataTool(BaseTool):
    name = "test_empty_tool"
    description = "A tool that returns empty data"

    async def _execute(self, tool_input: BaseToolInput) -> tuple[list, list]:
        return [], []


class MetadataTool(BaseTool):
    name = "test_metadata_tool"
    description = "A tool that returns metadata"

    async def _execute(self, tool_input: BaseToolInput) -> tuple[list, list, dict]:
        return [], [], {"empty": True, "source": "unit_test"}


class TestBaseTool:
    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_success_returns_success_true(self):
        tool = SuccessTool()
        result = await tool.run(BaseToolInput())
        assert result.success is True
        assert result.data == [{"id": 1, "value": "ok"}]
        assert len(result.evidence) == 1
        assert result.error is None

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_success_contains_trace_id(self):
        tool = SuccessTool()
        result = await tool.run(BaseToolInput())
        assert result.trace_id is not None
        assert result.trace_id.startswith("trace_")

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_tool_exception_returns_success_false(self):
        tool = ErrorTool()
        result = await tool.run(BaseToolInput())
        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.code == "TOOL_CUSTOM_ERROR"
        assert result.error.retryable is True

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_tool_exception_contains_trace_id(self):
        tool = ErrorTool()
        result = await tool.run(BaseToolInput())
        assert result.trace_id is not None

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_unexpected_exception_returns_internal_error(self):
        tool = CrashTool()
        result = await tool.run(BaseToolInput())
        assert result.success is False
        assert result.error is not None
        assert result.error.code == "TOOL_INTERNAL_ERROR"
        assert result.error.retryable is False

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_unexpected_exception_contains_trace_id(self):
        tool = CrashTool()
        result = await tool.run(BaseToolInput())
        assert result.trace_id is not None

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_empty_data_returns_success_with_empty_list(self):
        tool = EmptyDataTool()
        result = await tool.run(BaseToolInput())
        assert result.success is True
        assert result.data == []
        assert result.error is None

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_context_is_optional(self):
        tool = SuccessTool()
        result = await tool.run(BaseToolInput())
        assert result.success is True

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_run_accepts_default_input(self):
        tool = SuccessTool()
        result = await tool.run()
        assert result.success is True

    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_success_can_return_metadata(self):
        tool = MetadataTool()
        result = await tool.run(BaseToolInput())
        assert result.success is True
        assert result.metadata["empty"] is True
        assert result.metadata["source"] == "unit_test"
