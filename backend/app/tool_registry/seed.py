from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.contracts import BaseToolInput, ToolResult
from app.tool_registry.models import ToolDefinition, ToolPolicy, ToolVersion
from app.tools.action.work_order_draft_tool import WorkOrderDraftActionTool, WorkOrderDraftInput
from app.tools.analysis.ioc_summary_tool import AnalysisInput, IocSummaryAnalysisTool
from app.tools.query.alarm_tool import AlarmQueryTool
from app.tools.query.kpi_tool import KpiQueryTool
from app.tools.query.risk_tool import RiskQueryTool
from app.tools.query.work_order_tool import WorkOrderQueryTool
from app.utils.timezone import now_local


@dataclass(frozen=True)
class BuiltinTool:
    tool_key: str
    capability: str
    tool_type: str
    action_phase: str | None
    implementation_ref: str


BUILTIN_TOOLS = (
    BuiltinTool("kpi_query", "query.kpi", "query", None, "builtin.kpi_query"),
    BuiltinTool("alarm_query", "query.alarm", "query", None, "builtin.alarm_query"),
    BuiltinTool("risk_query", "query.risk", "query", None, "builtin.risk_query"),
    BuiltinTool("work_order_query", "query.work_order", "query", None, "builtin.work_order_query"),
    BuiltinTool("ioc_summary_analysis", "analysis.ioc_summary", "analysis", None, "builtin.ioc_summary_analysis"),
    BuiltinTool("work_order_draft", "action.work_order.draft", "action", "prepare", "builtin.work_order_draft"),
)


def seed_builtin_tools(db: Session, operator_id: str = "system") -> None:
    seeded_at = now_local()
    tools = _build_builtin_tool_instances()

    for builtin in BUILTIN_TOOLS:
        tool = tools[builtin.tool_key]

        definition = db.scalar(
            select(ToolDefinition).where(ToolDefinition.tool_key == builtin.tool_key)
        )
        if definition is None:
            definition = ToolDefinition(
                tool_key=builtin.tool_key,
                capability=builtin.capability,
                name=tool.name,
                description=tool.description,
                tool_type=builtin.tool_type,
                action_phase=builtin.action_phase,
                enabled=True,
                created_by=operator_id,
                updated_by=operator_id,
            )
            db.add(definition)
            db.flush()

        input_schema, output_schema = _schemas_for_tool(builtin.tool_key)
        versions = list(
            db.scalars(
                select(ToolVersion).where(ToolVersion.tool_id == definition.id)
            )
        )
        if not versions:
            version = ToolVersion(
                tool_id=definition.id,
                version="1.0.0",
                implementation_ref=builtin.implementation_ref,
                input_schema=input_schema,
                output_schema=output_schema,
                status="published",
                is_stable=True,
                gray_percentage=0,
                published_at=seeded_at,
                published_by=operator_id,
                created_by=operator_id,
                updated_by=operator_id,
            )
            db.add(version)
            db.flush()

        policies = list(
            db.scalars(
                select(ToolPolicy).where(ToolPolicy.tool_id == definition.id)
            )
        )
        if not policies:
            policy = ToolPolicy(
                tool_id=definition.id,
                version_id=None,
                tenant_id=None,
                role=None,
                decision="allow",
                rate_limit_per_minute=60,
                gray_percentage=0,
                requires_confirmation=False,
                enabled=True,
                updated_by=operator_id,
            )
            db.add(policy)
            db.flush()


def _build_builtin_tool_instances() -> dict[str, object]:
    client = MockIocApiClient()
    return {
        "kpi_query": KpiQueryTool(client=client),
        "alarm_query": AlarmQueryTool(client=client),
        "risk_query": RiskQueryTool(client=client),
        "work_order_query": WorkOrderQueryTool(client=client),
        "ioc_summary_analysis": IocSummaryAnalysisTool(),
        "work_order_draft": WorkOrderDraftActionTool(client=client),
    }


def _schemas_for_tool(tool_key: str) -> tuple[dict, dict]:
    input_model = {
        "ioc_summary_analysis": AnalysisInput,
        "work_order_draft": WorkOrderDraftInput,
    }.get(tool_key, BaseToolInput)
    return input_model.model_json_schema(), ToolResult.model_json_schema()
