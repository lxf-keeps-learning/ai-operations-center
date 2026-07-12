"""Sprint4.1 首批只读 Runtime Skill 定义。"""

from app.skills.contracts import SkillDefinition, SkillRiskLevel, SkillSideEffects
from app.skills.registry import SkillRegistry


OPERATION_ANALYSIS_SKILL = SkillDefinition(
    id="operation_analysis",
    name="运营分析",
    description="根据领域、时间维度和页面上下文生成结构化运营分析报告。",
    executor_id="operation_analysis_graph",
    required_inputs=[],
    optional_inputs=[
        "trigger_type",
        "domain",
        "active_tab",
        "time_dimension",
        "date",
        "company_id",
        "project_id",
        "user_question",
        "force_refresh",
    ],
    output_fields=[
        "record_id",
        "summary",
        "abnormal_items",
        "risk_items",
        "advice_items",
        "evidence",
        "analysis_basis",
    ],
    allowed_tools=[
        "kpi_query",
        "alarm_query",
        "risk_query",
        "work_order_query",
        "ioc_summary_analysis",
    ],
    risk_level=SkillRiskLevel.READ_ONLY,
    side_effects=SkillSideEffects(business_write=False, runtime_persistence=True),
    tags=["operation", "analysis", "report", "read_only"],
)


REPORT_DEEP_ANSWER_SKILL = SkillDefinition(
    id="report_deep_answer",
    name="报告深度问答",
    description="围绕指定分析报告回答追问，必要时通过 RAG 补充相关知识与依据。",
    executor_id="report_deep_answer_graph",
    required_inputs=["session_id", "report_id", "question"],
    optional_inputs=[],
    output_fields=[
        "conversation_id",
        "session_id",
        "runtime_session_id",
        "message_id",
        "answer",
        "question_scope",
        "answer_type",
        "evidence_refs",
        "used_rag",
        "rag_source_refs",
        "rag_sources",
    ],
    allowed_tools=[],
    risk_level=SkillRiskLevel.READ_ONLY,
    side_effects=SkillSideEffects(business_write=False, runtime_persistence=True),
    tags=["report", "chat", "rag", "read_only"],
)


def build_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(OPERATION_ANALYSIS_SKILL)
    registry.register(REPORT_DEEP_ANSWER_SKILL)
    return registry


skill_registry = build_skill_registry()
