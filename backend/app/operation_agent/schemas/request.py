from pydantic import BaseModel, Field


class OperationAnalyzeRequest(BaseModel):
    trigger_type: str = Field(default="tab_analysis", description="触发类型: page_load / tab_analysis / expert_chat / scheduled_daily")
    domain: str = Field(default="safety", description="分析领域: safety / maintenance / business / all")
    active_tab: str | None = Field(default=None, description="当前活跃 Tab")
    time_dimension: str = Field(default="month", description="时间维度: day / week / month / quarter / year")
    date: str | None = Field(default=None, description="分析日期")
    company_id: str | None = Field(default=None, description="公司 ID")
    project_id: str | None = Field(default=None, description="项目 ID")
    user_question: str | None = Field(default=None, description="用户附加问题")
