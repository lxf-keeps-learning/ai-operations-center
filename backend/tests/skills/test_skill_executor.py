import pytest
from pydantic import ValidationError

from app.skills.contracts import SkillExecutionContext
from app.skills.definitions import OPERATION_ANALYSIS_SKILL, REPORT_DEEP_ANSWER_SKILL
from app.skills.executor import execute_operation_analysis, execute_report_deep_answer, execute_skill


def test_operation_executor_reuses_existing_service(monkeypatch) -> None:
    captured = {}

    def fake_analyze(request, user_context, trace_id):
        captured["request"] = request
        captured["user_context"] = user_context
        captured["trace_id"] = trace_id
        return {
            "trace_id": trace_id,
            "record_id": 12,
            "final_answer": "# 运营分析",
            "abnormal_items": [{"id": "a1"}],
            "risk_items": [],
            "advice_items": [],
            "evidence": [{"source": "kpi_query"}],
            "errors": [],
        }

    monkeypatch.setattr("app.skills.executor.analyze_operation", fake_analyze)
    context = SkillExecutionContext(
        trace_id="trace_skill_001",
        user_id="user_1",
        tenant_id="tenant_1",
        roles=["operator"],
    )

    result = execute_operation_analysis(
        OPERATION_ANALYSIS_SKILL,
        {"domain": "safety", "time_dimension": "month"},
        context,
    )

    assert result.status == "success"
    assert result.trace_id == "trace_skill_001"
    assert result.data["record_id"] == 12
    assert result.data["summary"] == "# 运营分析"
    assert captured["request"].domain == "safety"
    assert captured["user_context"]["tenant_id"] == "tenant_1"


def test_report_answer_executor_reuses_existing_service(monkeypatch) -> None:
    def fake_send(**kwargs):
        return {
            "trace_id": kwargs["trace_id"],
            "conversation_id": "conv_1",
            "runtime_session_id": "runtime_1",
            "message_id": "msg_1",
            "final_answer": "根据报告证据得出结论。",
            "question_scope": "report_related",
            "answer_type": "rag_enhanced",
            "evidence_refs": ["ev_1"],
            "used_rag": True,
            "rag_source_refs": ["doc_1"],
            "rag_sources": [{"id": "doc_1", "title": "安全规范"}],
            "errors": [],
        }

    monkeypatch.setattr("app.skills.executor.send_chat_message", fake_send)
    result = execute_report_deep_answer(
        REPORT_DEEP_ANSWER_SKILL,
        {"session_id": "session_1", "report_id": 7, "question": "依据是什么？"},
        SkillExecutionContext(trace_id="trace_skill_002", user_id="user_1"),
    )

    assert result.status == "success"
    assert result.data["answer"] == "根据报告证据得出结论。"
    assert result.data["used_rag"] is True
    assert result.data["rag_sources"][0]["title"] == "安全规范"


def test_report_answer_executor_validates_required_inputs() -> None:
    with pytest.raises(ValidationError):
        execute_report_deep_answer(
            REPORT_DEEP_ANSWER_SKILL,
            {"report_id": 7, "question": "缺少会话"},
            SkillExecutionContext(),
        )


def test_unified_executor_rejects_undeclared_inputs() -> None:
    with pytest.raises(ValueError, match="Unsupported skill inputs: unsafe_param"):
        execute_skill(
            OPERATION_ANALYSIS_SKILL,
            {"domain": "safety", "unsafe_param": True},
            SkillExecutionContext(),
        )


def test_unified_executor_rejects_missing_required_inputs() -> None:
    with pytest.raises(ValueError, match="Missing required skill inputs: session_id"):
        execute_skill(
            REPORT_DEEP_ANSWER_SKILL,
            {"report_id": 7, "question": "依据是什么？"},
            SkillExecutionContext(),
        )
