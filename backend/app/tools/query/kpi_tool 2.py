from typing import Any

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.core.base_tool import BaseTool
from app.tool_center.core.schemas import BaseToolInput, Evidence
from app.tools.query._helpers import ensure_success, result_metadata


class KpiQueryTool(BaseTool):
    name = "kpi_query"
    description = "查询 IOC 指标数据，例如能耗、碳排放、设备可用率、告警处理率、工单完成率等。"

    def __init__(self, client: IocApiClient | None = None) -> None:
        super().__init__()
        self._client = client or MockIocApiClient()

    def _execute(self, tool_input: BaseToolInput) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        resp = self._client.get_kpis(filters=tool_input.filters)
        ensure_success(resp, code="KPI_QUERY_FAILED", message="KPI 查询失败")

        items = resp.data.get("items", [])
        evidence = []
        for item in items:
            evidence.append(
                Evidence(
                    source="mock_ioc_api",
                    source_type="kpi_api",
                    record_id=item.get("department"),
                    description=f"指标: {item.get('metric_name', '')}, 值: {item.get('value', '')}, 时间: {item.get('time_range', '')}, 部门: {item.get('department', '')}",
                )
            )
        return resp.data, evidence, result_metadata(resp)
