from pydantic import ValidationError
import pytest

from app.tool_center.core.schemas import BaseToolInput, Evidence, ToolContext, ToolError, ToolResult


class TestToolSchema:
    def test_tool_context_defaults(self):
        ctx = ToolContext()
        assert ctx.locale == "zh-CN"
        assert ctx.user_id is None

    def test_base_tool_input_has_default_context(self):
        inp = BaseToolInput()
        assert inp.context.locale == "zh-CN"

    def test_evidence_requires_source_and_source_type(self):
        ev = Evidence(source="ioc", source_type="alarm_api")
        assert ev.source == "ioc"
        assert ev.source_type == "alarm_api"

    def test_evidence_with_all_fields(self):
        ev = Evidence(
            source="ioc",
            source_type="kpi_api",
            record_id="rec_001",
            timestamp="2026-07-06T08:00:00",
            description="test evidence",
        )
        assert ev.record_id == "rec_001"

    def test_tool_error_defaults(self):
        err = ToolError(code="TOOL_ERROR", message="failed")
        assert err.retryable is False
        assert err.detail is None

    def test_tool_error_with_retryable(self):
        err = ToolError(code="TOOL_TIMEOUT", message="timeout", retryable=True)
        assert err.retryable is True

    def test_tool_result_success(self):
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.evidence == []

    def test_tool_result_failure(self):
        err = ToolError(code="TOOL_ERROR", message="failed")
        result = ToolResult(success=False, error=err, trace_id="trace_001")
        assert result.success is False
        assert result.error.code == "TOOL_ERROR"
        assert result.trace_id == "trace_001"

    def test_tool_result_with_evidence(self):
        ev = Evidence(source="ioc", source_type="kpi_api")
        result = ToolResult(success=True, evidence=[ev])
        assert len(result.evidence) == 1
        assert result.evidence[0].source == "ioc"

    def test_tool_invalid_missing_success(self):
        with pytest.raises(ValidationError):
            ToolResult()  # success is required
