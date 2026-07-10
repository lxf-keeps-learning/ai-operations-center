from typing import Any

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, Evidence
from app.tools.query._helpers import ensure_success, result_metadata


class RiskQueryTool(BaseTool):
    name = "risk_query"
    description = "查询 IOC 隐患风险数据，例如高风险隐患、巡检逾期、能耗异常趋势、安全生产隐患等。"

    def __init__(self, client: IocApiClient | None = None) -> None:
        super().__init__()
        self._client = client or MockIocApiClient()

    def _execute(self, tool_input: BaseToolInput) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        resp = self._client.get_risks(filters=tool_input.filters)
        ensure_success(resp, code="RISK_QUERY_FAILED", message="隐患查询失败")

        items = resp.data.get("items", [])
        evidence = []
        for item in items:
            evidence.append(
                Evidence(
                    source="mock_ioc_api",
                    source_type="risk_api",
                    record_id=item.get("risk_id"),
                    description=f"隐患: {item.get('title', '')}, 等级: {item.get('risk_level', '')}, 状态: {item.get('status', '')}, 责任人: {item.get('owner', '')}",
                )
            )
        return resp.data, evidence, result_metadata(resp)
