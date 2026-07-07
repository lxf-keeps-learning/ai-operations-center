from typing import Any

from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_data import ALARM_DATA, KPI_DATA, RISK_DATA, WORK_ORDER_DATA
from app.integrations.ioc.schema import IocApiResponse

# Sprint3 Mock IOC 过滤配置。
#
# 这里是 Mock Client 当前对外承诺的查询字段白名单。新增 Query Tool 过滤能力时，
# 优先在这里补字段，再补 Mock 数据和测试；不要在 Tool 内部悄悄解释未知字段。
KPI_FILTERS = {"department", "status", "metric_code", "time_range"}
ALARM_FILTERS = {"department", "status", "alarm_level", "alarm_type", "level", "alarm_id"}
RISK_FILTERS = {"department", "status", "risk_level", "level", "owner", "risk_id"}
WORK_ORDER_FILTERS = {"department", "status", "owner", "related_alarm_id", "related_risk_id"}


def _filter_by(records: list[Any], filters: dict | None, allowed_filters: set[str]) -> list[Any]:
    """按白名单字段过滤 Mock 数据。

    不支持的字段直接返回失败响应，避免 Graph/Tool 因字段拼错得到“看似成功”的空数据。
    """

    if not filters:
        return records
    unsupported = sorted(set(filters) - allowed_filters)
    if unsupported:
        raise ValueError(f"Unsupported filters: {', '.join(unsupported)}")

    result = list(records)
    for key, value in filters.items():
        if value is None:
            continue
        if key == "department":
            result = [r for r in result if getattr(r, "department", None) == value]
        elif key == "status":
            result = [r for r in result if getattr(r, "status", None) == value]
        elif key == "alarm_level":
            result = [r for r in result if getattr(r, "alarm_level", None) == value]
        elif key == "risk_level":
            result = [r for r in result if getattr(r, "risk_level", None) == value]
        elif key == "level":
            result = [
                r
                for r in result
                if (getattr(r, "alarm_level", None) or getattr(r, "risk_level", None)) == value
            ]
        elif key == "time_range":
            result = [r for r in result if getattr(r, "time_range", None) == value]
        elif key == "metric_code":
            result = [r for r in result if getattr(r, "metric_code", None) == value]
        elif key == "alarm_type":
            result = [r for r in result if getattr(r, "alarm_type", None) == value]
        elif key == "alarm_id":
            result = [r for r in result if getattr(r, "alarm_id", None) == value]
        elif key == "risk_id":
            result = [r for r in result if getattr(r, "risk_id", None) == value]
        elif key == "owner":
            result = [r for r in result if getattr(r, "owner", None) == value]
        elif key == "related_alarm_id":
            result = [r for r in result if getattr(r, "related_alarm_id", None) == value]
        elif key == "related_risk_id":
            result = [r for r in result if getattr(r, "related_risk_id", None) == value]
    return result


def _records_to_dict(records: list[Any]) -> dict[str, Any]:
    """统一 Mock IOC 列表返回结构，保持 items + total 契约。"""

    return {
        "items": [r.model_dump() for r in records],
        "total": len(records),
    }


def _response(records: list[Any], filters: dict | None, allowed_filters: set[str]) -> IocApiResponse:
    """把 Mock 查询结果包装成 IocApiResponse。

    metadata 中保留过滤条件、支持字段、是否空数据，方便上层 ToolResult 继续透传给 Graph。
    """

    try:
        items = _filter_by(records, filters, allowed_filters)
        data = _records_to_dict(items)
        return IocApiResponse(
            success=True,
            data=data,
            metadata={
                "filters": {
                    key: value for key, value in (filters or {}).items() if value is not None
                },
                "supported_filters": sorted(allowed_filters),
                "empty": data["total"] == 0,
            },
        )
    except Exception as e:
        return IocApiResponse(success=False, error=str(e))


class MockIocApiClient(IocApiClient):
    """本地开发和单元测试使用的 IOC Client。

    这里不调用数据库、不调用 LLM、不做业务分析，只模拟真实 IOC API 的数据访问契约。
    """

    def get_kpis(self, filters: dict | None = None) -> IocApiResponse:
        return _response(KPI_DATA, filters, KPI_FILTERS)

    def get_alarms(self, filters: dict | None = None) -> IocApiResponse:
        return _response(ALARM_DATA, filters, ALARM_FILTERS)

    def get_risks(self, filters: dict | None = None) -> IocApiResponse:
        return _response(RISK_DATA, filters, RISK_FILTERS)

    def get_work_orders(self, filters: dict | None = None) -> IocApiResponse:
        return _response(WORK_ORDER_DATA, filters, WORK_ORDER_FILTERS)
