from typing import Any

from pydantic import BaseModel, Field


class OperationAnalyzeResponse(BaseModel):
    trace_id: str = Field(description="请求追踪 ID")
    status: str = Field(description="处理状态: success / partial / failed")
    summary: str = Field(default="", description="运营分析摘要（Markdown）")
    abnormal_items: list[dict[str, Any]] = Field(default_factory=list, description="异常项列表")
    risk_items: list[dict[str, Any]] = Field(default_factory=list, description="风险项列表")
    advice_items: list[dict[str, Any]] = Field(default_factory=list, description="建议项列表")
    evidence: list[dict[str, Any]] = Field(default_factory=list, description="数据来源证据")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="处理过程中的错误")
