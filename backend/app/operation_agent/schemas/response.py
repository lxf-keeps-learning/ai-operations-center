"""
OperationAnalyzeResponse — 运营分析响应 DTO。

由 ApiResponse 包裹后返回给前端。
所有字段均为平铺结构，不含嵌套 data dict。
"""
from typing import Any

from pydantic import BaseModel, Field


class OperationAnalyzeResponse(BaseModel):
    """运营分析响应。"""
    trace_id: str = Field(description="请求追踪 ID，用于链路排查")
    status: str = Field(description="处理状态: success(成功) / partial(部分异常) / failed(失败)")
    summary: str = Field(default="", description="运营分析结论（Markdown 格式，前端可直接展示）")
    abnormal_items: list[dict[str, Any]] = Field(default_factory=list, description="识别的异常项列表")
    risk_items: list[dict[str, Any]] = Field(default_factory=list, description="风险项列表（预留字段）")
    advice_items: list[dict[str, Any]] = Field(default_factory=list, description="改进建议列表")
    evidence: list[dict[str, Any]] = Field(default_factory=list, description="数据来源证据链")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="处理过程中的错误记录")
