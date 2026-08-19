from typing import Any

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, Evidence
from app.tool_registry.contracts import ToolType
from app.tools.query._helpers import ensure_success, result_metadata


class AlarmQueryTool(BaseTool):
    name = "alarm_query"
    description = "查询 IOC 告警数据，例如高能耗异常、设备离线、压力异常、温度异常、安全告警等。"
    tool_type = ToolType.QUERY

    def __init__(self, client: IocApiClient | None = None) -> None:
        super().__init__()
        self._client = client or MockIocApiClient()

    async def _execute(self, tool_input: BaseToolInput) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        resp = await self._client.aget_alarms(filters=tool_input.filters)
        ensure_success(resp, code="ALARM_QUERY_FAILED", message="告警查询失败")

        items = resp.data.get("items", [])
        evidence = []
        for item in items:
            evidence.append(
                Evidence(
                    source="mock_ioc_api",
                    source_type="alarm_api",
                    record_id=item.get("alarm_id"),
                    description=f"告警: {item.get('title', '')}, 等级: {item.get('alarm_level', '')}, 状态: {item.get('status', '')}, 时间: {item.get('occurred_at', '')}",
                )
            )
        return resp.data, evidence, result_metadata(resp)
