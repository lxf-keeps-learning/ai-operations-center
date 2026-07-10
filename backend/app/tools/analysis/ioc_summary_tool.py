from typing import Any

from pydantic import Field, ValidationError

from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolException
from app.tool_center.contracts import BaseToolInput, Evidence


def _count(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        key = str(item.get(field) or "unknown")
        result[key] = result.get(key, 0) + 1
    return result


def _calc_risk_score(
    kpi_data: dict | None,
    alarm_data: dict | None,
    risk_data: dict | None,
    work_order_data: dict | None,
) -> tuple[int, str]:
    score = 0

    alarms = (alarm_data or {}).get("items", [])
    for a in alarms:
        level = a.get("alarm_level", "")
        if level == "critical":
            score += 5
        elif level == "high":
            score += 3
        elif level == "medium":
            score += 1

    risks = (risk_data or {}).get("items", [])
    for r in risks:
        level = r.get("risk_level", "")
        if level == "high":
            score += 4
        elif level == "medium":
            score += 2

    kpis = (kpi_data or {}).get("items", [])
    for k in kpis:
        status = k.get("status", "")
        if status == "critical":
            score += 4
        elif status == "warning":
            score += 2

    wos = (work_order_data or {}).get("items", [])
    for w in wos:
        if w.get("status") == "pending":
            score += 1

    if score >= 20:
        level = "high"
    elif score >= 10:
        level = "medium"
    else:
        level = "low"

    return score, level


class AnalysisInput(BaseToolInput):
    kpi_data: dict[str, Any] | None = Field(default=None, description="KpiQueryTool 的 data")
    alarm_data: dict[str, Any] | None = Field(default=None, description="AlarmQueryTool 的 data")
    risk_data: dict[str, Any] | None = Field(default=None, description="RiskQueryTool 的 data")
    work_order_data: dict[str, Any] | None = Field(
        default=None,
        description="WorkOrderQueryTool 的 data",
    )


class IocSummaryAnalysisTool(BaseTool):
    name = "ioc_summary_analysis"
    description = (
        "对 IOC 查询结果做结构化聚合分析"
        "（KPI 状态统计、告警等级分组、风险评分），"
        "不调用 LLM。"
    )

    def _execute(
        self,
        tool_input: BaseToolInput,
    ) -> tuple[dict | None, list[Evidence], dict[str, Any]]:
        inp = self._parse_input(tool_input)

        kpi_items = (inp.kpi_data or {}).get("items", [])
        alarm_items = (inp.alarm_data or {}).get("items", [])
        risk_items = (inp.risk_data or {}).get("items", [])
        wo_items = (inp.work_order_data or {}).get("items", [])

        kpi_by_status = _count(kpi_items, "status")
        alarm_by_level = _count(alarm_items, "alarm_level")
        risk_by_level = _count(risk_items, "risk_level")
        wo_by_status = _count(wo_items, "status")

        score, level = _calc_risk_score(
            inp.kpi_data,
            inp.alarm_data,
            inp.risk_data,
            inp.work_order_data,
        )

        data = {
            "kpi": {
                "total": len(kpi_items),
                "by_status": kpi_by_status,
            },
            "alarm": {
                "total": len(alarm_items),
                "by_level": alarm_by_level,
            },
            "risk": {
                "total": len(risk_items),
                "by_level": risk_by_level,
            },
            "work_order": {
                "total": len(wo_items),
                "by_status": wo_by_status,
            },
            "risk_score": score,
            "risk_level": level,
        }

        summary = (
            f"KPI {len(kpi_items)} 条, 告警 {len(alarm_items)} 条, "
            f"隐患 {len(risk_items)} 条, "
            f"工单 {len(wo_items)} 条, 风险评分 {score}/{level}"
        )
        evidence = [
            Evidence(
                source="analysis_engine",
                source_type="summary",
                description=summary,
            )
        ]

        metadata = {
            "source": "analysis_engine",
            "empty": not any((kpi_items, alarm_items, risk_items, wo_items)),
            "input_totals": {
                "kpi": len(kpi_items),
                "alarm": len(alarm_items),
                "risk": len(risk_items),
                "work_order": len(wo_items),
            },
        }

        return data, evidence, metadata

    def _parse_input(self, tool_input: BaseToolInput) -> AnalysisInput:
        if isinstance(tool_input, AnalysisInput):
            return tool_input

        payload = dict(tool_input.filters)
        payload.pop("context", None)
        payload.pop("filters", None)

        try:
            return AnalysisInput(
                context=tool_input.context,
                filters=tool_input.filters,
                **payload,
            )
        except ValidationError as e:
            raise ToolException(
                code="ANALYSIS_VALIDATION_ERROR",
                message="分析 Tool 参数格式错误",
                detail={"errors": e.errors()},
            ) from e
