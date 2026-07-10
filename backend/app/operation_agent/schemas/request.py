"""
OperationAnalyzeRequest — 运营分析请求 DTO。

前端调用同步或 SSE 运营分析接口时传入的统一请求体。
所有字段均有默认值，最小调用只需 body = {}。
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.operation_agent.state import OperationDomain, TriggerType

TimeDimension = Literal["day", "week", "month", "quarter", "year"]


class OperationAnalyzeRequest(BaseModel):
    """运营分析请求参数。"""
    trigger_type: TriggerType = Field(
        default="tab_analysis",
        description="触发类型: page_load / tab_analysis / expert_chat / scheduled_daily",
    )
    domain: OperationDomain = Field(
        default="safety",
        description=(
            "分析领域: safety(本质安全) / maintenance(设备运维) / "
            "business(经营改善) / capability(能力提升) / all(全部)"
        ),
    )
    active_tab: str | None = Field(
        default=None,
        max_length=128,
        description="当前活跃 Tab 名称",
    )
    time_dimension: TimeDimension = Field(
        default="month",
        description="时间维度: day / week / month / quarter / year",
    )
    date: str | None = Field(default=None, max_length=32, description="分析日期，如 2026-07")
    company_id: str | None = Field(default=None, max_length=64, description="公司 ID")
    project_id: str | None = Field(default=None, max_length=64, description="项目 ID")
    user_question: str | None = Field(
        default=None,
        max_length=2000,
        description="用户输入的附加问题",
    )
    force_refresh: bool = Field(
        default=False,
        description="是否绕过 30 分钟缓存重新生成报告",
    )
