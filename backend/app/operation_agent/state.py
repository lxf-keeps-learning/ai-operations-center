from typing import Any, Literal, NotRequired, TypedDict

OperationDomain = Literal["safety", "maintenance", "business", "all"]
TriggerType = Literal["page_load", "tab_analysis", "expert_chat", "scheduled_daily"]
AnalysisMode = Literal["dashboard_snapshot", "domain_focus", "qa"]


class OperationState(TypedDict, total=False):
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
