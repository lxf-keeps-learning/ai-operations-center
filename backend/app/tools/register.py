from app.integrations.ioc.mock_client import MockIocApiClient
from app.tool_center.registry import registry
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
    registry.register(KpiQueryTool(client=client))
    registry.register(AlarmQueryTool(client=client))
    registry.register(RiskQueryTool(client=client))
    registry.register(WorkOrderQueryTool(client=client))
    registry.register(IocSummaryAnalysisTool())
    registry.register(WorkOrderDraftActionTool(client=client))
