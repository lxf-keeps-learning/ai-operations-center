from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.registry import registry
from app.tool_registry.executor_catalog import executor_catalog
from app.tool_registry.seed import BUILTIN_TOOLS
from app.tools.action.work_order_draft_tool import WorkOrderDraftActionTool
from app.tools.analysis.ioc_summary_tool import IocSummaryAnalysisTool
from app.tools.query.alarm_tool import AlarmQueryTool
from app.tools.query.kpi_tool import KpiQueryTool
from app.tools.query.risk_tool import RiskQueryTool
from app.tools.query.work_order_tool import WorkOrderQueryTool


def register_all_tools() -> None:
    """注册 Sprint3 当前已完成的 Tool。

    Query Tool 统一使用 MockIocApiClient，让本地开发和测试不依赖真实 IOC 系统。
    后续切换真实 IOC API 时，优先把 client 的构建逻辑收敛到这里或工厂函数中。
    """

    client = MockIocApiClient()
    tools = {
        "kpi_query": KpiQueryTool(client=client),
        "alarm_query": AlarmQueryTool(client=client),
        "risk_query": RiskQueryTool(client=client),
        "work_order_query": WorkOrderQueryTool(client=client),
        "ioc_summary_analysis": IocSummaryAnalysisTool(),
        "work_order_draft": WorkOrderDraftActionTool(client=client),
    }

    executor_catalog.clear()
    for builtin in BUILTIN_TOOLS:
        tool = tools[builtin.tool_key]
        registry.register(tool)
        executor_catalog.register(builtin.implementation_ref, tool)
