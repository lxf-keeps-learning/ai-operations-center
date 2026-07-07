"""
OperationState — 运营分析智能体的数据契约。

State 是 Graph 中所有 Node 之间传递数据的唯一类型。
每个 Node 从 State 中读取自己需要的字段，并把处理结果写回 State。

设计原则：
- 不保存 ORM 对象、数据库连接或前端组件。
- 所有字段都是 JSON 可序列化的基本类型。
- error 列表记录各 Node 的处理异常，但不会使 Graph 崩溃。
"""
from typing import Any, Literal, NotRequired, TypedDict

# ── 类型字面量 ──────────────────────────────────────
OperationDomain = Literal["safety", "maintenance", "business", "all"]
TriggerType = Literal["page_load", "tab_analysis", "expert_chat", "scheduled_daily"]
AnalysisMode = Literal["dashboard_snapshot", "domain_focus", "qa"]


class OperationState(TypedDict, total=False):
    """
    OperationState 字段说明：

    trace_id        — 全链路追踪 ID，在 InitContextNode 中生成
    trigger_type    — 触发类型（页面加载/ Tab 切换/ 专家问答/ 定时任务）
    analysis_mode   — 分析模式（快照/ 领域聚焦/ 问答），由 trigger_type 映射
    domain          — 分析领域（安全/ 设备/ 经营/ 全部）
    user_question   — 用户输入的附加问题

    user_context    — 用户身份、角色信息，由 API 传入
    page_context    — 页面筛选条件（domain、日期、时间维度）

    raw_data        — 从 Tool Center 或 Mock 获取的原始数据
    metrics         — 从 raw_data 提取的结构化指标列表

    abnormal_items  — DetectAbnormalNode 输出的异常项列表
    reason_analysis — AnalyzeReasonNode 生成的异常原因分析文本
    risk_items      — 风险项列表（当前为预留字段）
    advice_items    — GenerateAdviceNode 生成的改进建议列表

    evidence        — 数据来源证据链，贯穿整个分析过程
    final_answer    — SummaryNode 生成的最终 Markdown 结论

    errors          — 各 Node 处理过程中的错误记录（不阻塞后续节点）
    """
    trace_id: str

    trigger_type: TriggerType
    analysis_mode: AnalysisMode
    domain: NotRequired[OperationDomain]
    user_question: NotRequired[str | None]

    user_context: dict[str, Any]
    page_context: dict[str, Any]

    raw_data: dict[str, Any]
    metrics: list[dict[str, Any]]

    abnormal_items: list[dict[str, Any]]
    reason_analysis: str
    risk_items: list[dict[str, Any]]
    advice_items: list[dict[str, Any]]

    evidence: list[dict[str, Any]]
    final_answer: str

    errors: list[dict[str, Any]]
