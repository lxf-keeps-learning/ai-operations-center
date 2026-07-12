# IOC 查询结果聚合分析 Tool
#
# 职责：对 KPI / 告警 / 隐患 / 工单四个 Query Tool 的原始返回做确定性聚合统计，
#       不调用 LLM、不依赖任何外部服务。
#
# 设计原则 — 确定性聚合与 LLM 推理分离：
#   本 Tool 只做纯计算（计数、分组、风险打分），结果以结构化数据写入 state。
#   LLM 节点（analyze_reason / generate_advice）拿到的是 {risk_score, by_status}
#   这样的确定事实，不需要自己算一遍总数，避免幻觉和 token 浪费。
#
# 输入：四个 Query Tool 的 data 字段（items + total 结构）
# 输出：结构化聚合摘要 + risk_score + risk_level
# 性质：纯函数，相同输入永远得到相同输出

from typing import Any

from pydantic import Field, ValidationError

from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolException
from app.tool_center.contracts import BaseToolInput, Evidence


def _count(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    """按指定字段分组计数，如按 status 分组统计各状态数量。"""
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
    """根据 KPI/告警/隐患/工单数据计算综合风险评分和等级。

    评分规则（可调整）：
      critical 告警 +5, high +3, medium +1
      high 隐患 +4, medium +2
      critical KPI +4, warning +2
      pending 工单 +1
    等级阈值：>=20 high, >=10 medium, <10 low
    """
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
    """强类型输入，接收四个 Query Tool 的 data 作为聚合源。"""
    kpi_data: dict[str, Any] | None = Field(default=None, description="KpiQueryTool 的 data")
    alarm_data: dict[str, Any] | None = Field(default=None, description="AlarmQueryTool 的 data")
    risk_data: dict[str, Any] | None = Field(default=None, description="RiskQueryTool 的 data")
    work_order_data: dict[str, Any] | None = Field(
        default=None,
        description="WorkOrderQueryTool 的 data",
    )


class IocSummaryAnalysisTool(BaseTool):
    """对 IOC 查询结果做结构化聚合分析，不调用 LLM。

    接收 KpiQuery / AlarmQuery / RiskQuery / WorkOrderQuery 四个 Tool
    的 data，输出聚合统计和风险评分，供下游 LLM 节点做自然语言分析。
    """
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
        """执行聚合分析。

        1) 提取四个来源的 items 列表
        2) 分组计数（KPI 按状态、告警按等级、隐患按等级、工单按状态）
        3) 计算综合风险评分
        4) 返回结构化 data + evidence + metadata
        """
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
            "kpi": {"total": len(kpi_items), "by_status": kpi_by_status},
            "alarm": {"total": len(alarm_items), "by_level": alarm_by_level},
            "risk": {"total": len(risk_items), "by_level": risk_by_level},
            "work_order": {"total": len(wo_items), "by_status": wo_by_status},
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
        """兼容两种传入方式：直接 AnalysisInput 实例，或通过 filters 字典传参。"""
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
