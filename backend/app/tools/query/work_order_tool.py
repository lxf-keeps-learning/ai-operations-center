from typing import Any

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.core.base_tool import BaseTool
from app.tool_center.core.schemas import BaseToolInput, Evidence
from app.tools.query._helpers import ensure_success, result_metadata


class WorkOrderQueryTool(BaseTool):
    name = "work_order_query"
    description = "查询 IOC 工单数据，例如处理中工单、已完成工单、与告警或隐患关联的工单等。"

    def __init__(self, client: IocApiClient | None = None) -> None:
        super().__init__()
        self._client = client or MockIocApiClient()

    def _execute(self, tool_input: BaseToolInput) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        resp = self._client.get_work_orders(filters=tool_input.filters)
        ensure_success(resp, code="WORK_ORDER_QUERY_FAILED", message="工单查询失败")

        items = resp.data.get("items", [])
        evidence = []
        for item in items:
            evidence.append(
                Evidence(
                    source="mock_ioc_api",
                    source_type="work_order_api",
                    record_id=item.get("work_order_id"),
                    description=f"工单: {item.get('title', '')}, 状态: {item.get('status', '')}, 负责人: {item.get('owner', '')}, 创建时间: {item.get('created_at', '')}",
                )
            )
        return resp.data, evidence, result_metadata(resp)
