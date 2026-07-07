"""
OperationAnalyzeRequest — 运营分析请求 DTO。

前端调用 POST /api/v1/operation/analyze 时传入的请求体。
所有字段均有默认值，最小调用只需 body = {}。
"""
from pydantic import BaseModel, Field


class OperationAnalyzeRequest(BaseModel):
    """运营分析请求参数。"""
    trigger_type: str = Field(
        default="tab_analysis",
        description="触发类型: page_load / tab_analysis / expert_chat / scheduled_daily",
    )
    domain: str = Field(
        default="safety",
        description="分析领域: safety(本质安全) / maintenance(设备运维) / business(经营改善) / all(全部)",
    )
    active_tab: str | None = Field(default=None, description="当前活跃 Tab 名称")
    time_dimension: str = Field(default="month", description="时间维度: day / week / month / quarter / year")
    date: str | None = Field(default=None, description="分析日期，如 2026-07")
    company_id: str | None = Field(default=None, description="公司 ID")
    project_id: str | None = Field(default=None, description="项目 ID")
    user_question: str | None = Field(default=None, description="用户输入的附加问题")
