#!/usr/bin/env python3
"""
Tool Center 人工验收脚本。

用法：
    cd backend && source .venv/bin/activate
    python scripts/verify_tool_center.py

正常输出应看到所有步骤的 ✅。
如果某一步出错，会继续执行后续步骤，并在汇总中显示 ❌ + 错误详情。
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tool_center.exceptions import ToolNotFoundError
from app.tool_center.contracts import BaseToolInput, ToolResult
from app.tool_center.registry import registry
from app.tools.analysis.ioc_summary_tool import AnalysisInput
from app.tools.register import register_all_tools

REQUIRED_TOOLS = (
    "kpi_query",
    "alarm_query",
    "risk_query",
    "work_order_query",
    "ioc_summary_analysis",
    "work_order_draft",
)


@dataclass
class StepReport:
    number: int
    desc: str
    passed: bool
    notes: list[str] = field(default_factory=list)
    error: str | None = None


class Verifier:
    def __init__(self) -> None:
        self.reports: list[StepReport] = []
        self._current_notes: list[str] = []

    def note(self, msg: str) -> None:
        print(f"  ✅ {msg}")
        self._current_notes.append(msg)

    def run_step(self, number: int, desc: str, fn: Callable[[], None]) -> None:
        print(f"\n[{number:02d}] {desc}")
        self._current_notes = []
        try:
            fn()
            self.reports.append(
                StepReport(
                    number=number,
                    desc=desc,
                    passed=True,
                    notes=list(self._current_notes),
                )
            )
        except Exception as e:
            print(f"  ❌ {e}")
            self.reports.append(
                StepReport(
                    number=number,
                    desc=desc,
                    passed=False,
                    notes=list(self._current_notes),
                    error=str(e),
                )
            )

    def summary(self) -> int:
        print()
        print("=" * 60)
        passed = sum(1 for report in self.reports if report.passed)
        total = len(self.reports)
        print(f"  通过步骤: {passed}/{total}")

        failed = [report for report in self.reports if not report.passed]
        if failed:
            print("  失败详情:")
            for report in failed:
                print(f"    [Step {report.number:02d}] {report.desc}: {report.error}")
            print("=" * 60)
            return 1

        print("  🎉 全部通过，Tool Center 验收完成")
        print("=" * 60)
        return 0


def run_tool(name: str, filters: dict | None = None) -> ToolResult:
    return registry.get(name).run(BaseToolInput(filters=filters or {}))


def require_success(result: ToolResult, label: str) -> None:
    assert result.success is True, f"{label} success=false: {result.error}"
    assert result.data is not None, f"{label} data 为空"


def short_trace(result: ToolResult) -> str:
    assert result.trace_id, "trace_id 为空"
    return f"{result.trace_id[:20]}..."


def main() -> int:
    verifier = Verifier()

    print("=" * 60)
    print("  Tool Center 验收脚本")
    print("=" * 60)

    def verify_registration() -> None:
        register_all_tools()
        names = registry.list_tools()
        missing = sorted(set(REQUIRED_TOOLS) - set(names))
        assert not missing, f"缺少 Tool: {', '.join(missing)}"
        verifier.note(f"已注册 {len(names)} 个 Tool: {names}")

    def verify_kpi_query() -> None:
        result = run_tool("kpi_query", {"metric_code": "energy_consumption"})
        require_success(result, "KPI Query")
        assert result.data["total"] > 0, "total=0"
        assert len(result.evidence) > 0, "evidence 为空"
        assert result.metadata["source"] == "mock_ioc_api"
        verifier.note(
            f"查到 {result.data['total']} 条, "
            f"evidence {len(result.evidence)} 条, trace_id={short_trace(result)}"
        )

    def verify_alarm_query() -> None:
        result = run_tool("alarm_query", {"alarm_level": "high"})
        require_success(result, "Alarm Query")
        assert result.data["total"] > 0
        assert len(result.evidence) > 0
        verifier.note(f"查到 {result.data['total']} 条告警")

    def verify_risk_query() -> None:
        result = run_tool("risk_query", {"status": "pending"})
        require_success(result, "Risk Query")
        assert result.data["total"] > 0
        verifier.note(f"查到 {result.data['total']} 条隐患")

    def verify_work_order_query() -> None:
        result = run_tool("work_order_query", {"status": "in_progress"})
        require_success(result, "WorkOrder Query")
        assert result.data["total"] > 0
        verifier.note(f"查到 {result.data['total']} 条工单")

    def verify_analysis() -> None:
        kpi_r = run_tool("kpi_query")
        alarm_r = run_tool("alarm_query")
        risk_r = run_tool("risk_query")
        wo_r = run_tool("work_order_query")
        for label, result in (
            ("KPI Query", kpi_r),
            ("Alarm Query", alarm_r),
            ("Risk Query", risk_r),
            ("WorkOrder Query", wo_r),
        ):
            require_success(result, label)

        result = registry.get("ioc_summary_analysis").run(
            AnalysisInput(
                kpi_data=kpi_r.data,
                alarm_data=alarm_r.data,
                risk_data=risk_r.data,
                work_order_data=wo_r.data,
            )
        )
        require_success(result, "IocSummaryAnalysis")
        assert "risk_score" in result.data
        assert "risk_level" in result.data
        assert result.metadata["source"] == "analysis_engine"
        verifier.note(
            f"风险评分: {result.data['risk_score']}, "
            f"等级: {result.data['risk_level']}"
        )
        verifier.note(
            f"KPI={result.data['kpi']['total']} "
            f"告警={result.data['alarm']['total']} "
            f"隐患={result.data['risk']['total']} "
            f"工单={result.data['work_order']['total']}"
        )

    def verify_action_draft() -> None:
        result = registry.get("work_order_draft").run(
            BaseToolInput(
                filters={
                    "source_type": "alarm",
                    "source_id": "alarm_001",
                    "title": "处理冷站出水温度异常",
                    "description": "来自验收脚本",
                    "priority": "high",
                }
            )
        )
        require_success(result, "WorkOrderDraft")
        assert result.data["requires_human_confirmation"] is True
        assert result.data["status"] == "draft"
        assert result.metadata["requires_human_confirmation"] is True
        verifier.note(
            f"草稿: status={result.data['status']}, "
            f"需确认={result.data['requires_human_confirmation']}"
        )
        verifier.note(
            f"来源: {result.data['draft']['source_type']}"
            f"({result.data['draft']['source_id']}), "
            f"{result.data['draft']['source_title']}"
        )

    def verify_empty_analysis() -> None:
        result = registry.get("ioc_summary_analysis").run(AnalysisInput())
        require_success(result, "IocSummaryAnalysis empty")
        assert result.data["risk_score"] == 0
        assert result.data["risk_level"] == "low"
        assert result.metadata["empty"] is True
        verifier.note(
            f"空数据: 评分={result.data['risk_score']}, "
            f"等级={result.data['risk_level']}"
        )

    def verify_missing_tool() -> None:
        try:
            registry.get("nonexistent")
        except ToolNotFoundError as e:
            verifier.note(f"正确抛出: {e}")
            return
        raise AssertionError("没有抛出 ToolNotFoundError")

    verifier.run_step(0, "注册所有 Tool", verify_registration)
    verifier.run_step(1, "KPI Query Tool — 查询综合能耗指标", verify_kpi_query)
    verifier.run_step(2, "Alarm Query Tool — 查询 high 级别告警", verify_alarm_query)
    verifier.run_step(3, "Risk Query Tool — 查询 pending 隐患", verify_risk_query)
    verifier.run_step(4, "WorkOrder Query Tool — 查询处理中工单", verify_work_order_query)
    verifier.run_step(5, "IocSummaryAnalysis Tool — 聚合分析", verify_analysis)
    verifier.run_step(6, "WorkOrderDraft Action Tool — 生成工单草稿", verify_action_draft)
    verifier.run_step(7, "空数据场景 — Analysis Tool 接收空数据", verify_empty_analysis)
    verifier.run_step(8, "错误场景 — 获取不存在的 Tool", verify_missing_tool)

    return verifier.summary()


if __name__ == "__main__":
    raise SystemExit(main())
