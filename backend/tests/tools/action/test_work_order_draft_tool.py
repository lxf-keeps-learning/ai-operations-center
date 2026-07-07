from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.core.schemas import BaseToolInput
from app.tool_center.registry import registry
from app.tools.action.work_order_draft_tool import WorkOrderDraftActionTool, WorkOrderDraftInput
from app.tools.register import register_all_tools


class TestWorkOrderDraftActionTool:
    def setup_method(self):
        self.client = MockIocApiClient()
        self.tool = WorkOrderDraftActionTool(client=self.client)

    def test_generates_draft_from_alarm(self):
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_001",
            title="处理冷站出水温度异常",
            description="基于告警 alarm_001 生成工单",
            priority="high",
        )
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["requires_human_confirmation"] is True
        assert result.data["status"] == "draft"
        assert result.data["draft"]["source_type"] == "alarm"
        assert result.data["draft"]["source_id"] == "alarm_001"
        assert result.data["draft"]["source_title"] == "冷站出水温度异常"

    def test_generates_draft_from_risk(self):
        inp = WorkOrderDraftInput(
            source_type="risk",
            source_id="risk_001",
            title="2号泵振动监测与维修",
            description="基于隐患 risk_001 生成工单",
            priority="high",
        )
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["requires_human_confirmation"] is True
        assert result.data["draft"]["source_type"] == "risk"
        assert result.data["draft"]["source_id"] == "risk_001"

    def test_generates_draft_without_source_lookup(self):
        inp = WorkOrderDraftInput(
            source_type="manual",
            source_id="manual_001",
            title="定期设备巡检",
            description="手动创建工单",
            priority="medium",
        )
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["draft"]["source_type"] == "manual"
        assert result.data["draft"]["source_title"] == ""

    def test_accepts_generic_tool_input_filters(self):
        inp = BaseToolInput(
            filters={
                "source_type": "alarm",
                "source_id": "alarm_001",
                "title": "处理冷站出水温度异常",
                "description": "基于告警 alarm_001 生成工单",
                "priority": "high",
            }
        )
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["draft"]["source_id"] == "alarm_001"

    def test_invalid_source_type_returns_error(self):
        inp = WorkOrderDraftInput(
            source_type="invalid",
            source_id="x",
            title="test",
            description="test",
        )
        result = self.tool.run(inp)
        assert result.success is False
        assert result.error.code == "ACTION_VALIDATION_ERROR"

    def test_invalid_priority_returns_error(self):
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_001",
            title="test",
            description="test",
            priority="urgent",
        )
        result = self.tool.run(inp)
        assert result.success is False
        assert result.error.code == "ACTION_VALIDATION_ERROR"

    def test_missing_source_returns_error(self):
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_missing",
            title="test",
            description="test",
        )
        result = self.tool.run(inp)
        assert result.success is False
        assert result.error.code == "ACTION_SOURCE_NOT_FOUND"

    def test_returns_evidence(self):
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_001",
            title="test",
            description="test",
        )
        result = self.tool.run(inp)
        assert len(result.evidence) > 0
        assert result.evidence[0].source == "action_engine"

    def test_returns_trace_id(self):
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_001",
            title="test",
            description="test",
        )
        result = self.tool.run(inp)
        assert result.trace_id is not None

    def test_registered_in_registry(self):
        register_all_tools()
        tool = registry.get("work_order_draft")
        assert tool.name == "work_order_draft"

    def test_no_real_api_call(self):
        """Action Tool 不调用真实写接口"""
        inp = WorkOrderDraftInput(
            source_type="alarm",
            source_id="alarm_001",
            title="test",
            description="test",
        )
        result = self.tool.run(inp)
        assert result.success is True
        assert result.data["action_type"] == "create_work_order_draft"
