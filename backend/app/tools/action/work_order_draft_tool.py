from typing import Any

from pydantic import Field, ValidationError

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolException
from app.tool_center.contracts import BaseToolInput, Evidence


class WorkOrderDraftInput(BaseToolInput):
    source_type: str = Field(description="来源类型: alarm / risk / manual")
    source_id: str = Field(description="来源 ID，如 alarm_id / risk_id")
    title: str = Field(description="工单标题")
    description: str = Field(description="工单描述")
    priority: str = Field(default="medium", description="优先级: high / medium / low")
    suggested_assignee: str | None = Field(default=None, description="建议负责人")


class WorkOrderDraftActionTool(BaseTool):
    name = "work_order_draft"
    description = (
        "根据告警或隐患生成工单草稿，"
        "不直接创建真实工单，必须人工确认后才能执行。"
    )
    allowed_priorities = {"high", "medium", "low"}
    allowed_source_types = {"alarm", "risk", "manual"}

    def __init__(self, client: IocApiClient | None = None) -> None:
        super().__init__()
        self._client = client or MockIocApiClient()

    def _execute(
        self,
        tool_input: BaseToolInput,
    ) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        inp = self._parse_input(tool_input)

        if inp.source_type not in self.allowed_source_types:
            raise ToolException(
                code="ACTION_VALIDATION_ERROR",
                message=f"不支持的 source_type: {inp.source_type}",
                detail={"allowed_source_types": sorted(self.allowed_source_types)},
            )
        if inp.priority not in self.allowed_priorities:
            raise ToolException(
                code="ACTION_VALIDATION_ERROR",
                message=f"不支持的 priority: {inp.priority}",
                detail={"allowed_priorities": sorted(self.allowed_priorities)},
            )

        source_title = self._lookup_source_title(inp)

        data = {
            "action_type": "create_work_order_draft",
            "requires_human_confirmation": True,
            "status": "draft",
            "draft": {
                "title": inp.title,
                "description": inp.description,
                "priority": inp.priority,
                "source_type": inp.source_type,
                "source_id": inp.source_id,
                "source_title": source_title,
                "suggested_assignee": inp.suggested_assignee,
            },
        }

        evidence = [
            Evidence(
                source="action_engine",
                source_type="work_order_draft",
                record_id=inp.source_id,
                description=(
                    f"基于 {inp.source_type}({inp.source_id}) 生成工单草稿: {inp.title}"
                ),
            )
        ]

        metadata = {
            "source": "action_engine",
            "requires_human_confirmation": True,
            "source_type": inp.source_type,
        }

        return data, evidence, metadata

    def _parse_input(self, tool_input: BaseToolInput) -> WorkOrderDraftInput:
        if isinstance(tool_input, WorkOrderDraftInput):
            return tool_input

        payload = dict(tool_input.filters)
        payload.pop("context", None)
        payload.pop("filters", None)

        try:
            return WorkOrderDraftInput(
                context=tool_input.context,
                filters=tool_input.filters,
                **payload,
            )
        except ValidationError as e:
            raise ToolException(
                code="ACTION_VALIDATION_ERROR",
                message="工单草稿参数不完整或格式错误",
                detail={"errors": e.errors()},
            ) from e

    def _lookup_source_title(self, inp: WorkOrderDraftInput) -> str:
        if inp.source_type == "manual":
            return ""

        if inp.source_type == "alarm":
            resp = self._client.get_alarms(filters={"alarm_id": inp.source_id})
        else:
            resp = self._client.get_risks(filters={"risk_id": inp.source_id})

        if not resp.success:
            raise ToolException(
                code="ACTION_SOURCE_LOOKUP_FAILED",
                message="动作来源查询失败",
                detail={
                    "reason": resp.error,
                    "source_type": inp.source_type,
                    "source_id": inp.source_id,
                },
            )

        items = resp.data.get("items", [])
        if not items:
            raise ToolException(
                code="ACTION_SOURCE_NOT_FOUND",
                message=f"动作来源不存在: {inp.source_type}({inp.source_id})",
                detail={"source_type": inp.source_type, "source_id": inp.source_id},
            )

        return items[0].get("title", "")
