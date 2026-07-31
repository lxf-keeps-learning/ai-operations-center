from app.report_chat_agent.context_budget import build_context_budget


def test_context_budget_keeps_question_and_report_before_history():
    result = build_context_budget(
        user_question="请判断当前报告的高风险原因",
        report_context={"summary": "报告核心结论" * 500},
        evidence=[{"content": "证据" * 500}],
        retrieved_context=[{"content": "报告检索片段" * 500}],
        merged_context=[],
        memory_context=[{"value": {"content": "用户偏好" * 500}}],
        rag_results=[{"content": "知识库内容" * 500}],
        chat_history=[{"role": "user", "content": "历史问题" * 500}],
        input_budget=500,
    )

    assert result["user_question"] == "请判断当前报告的高风险原因"
    assert result["report_context"]
    assert result["estimated_tokens"] <= 500
    assert result["truncated"] is True


def test_context_budget_reports_each_context_for_prompt_observability():
    result = build_context_budget(
        user_question="问题",
        report_context={"summary": "报告"},
        evidence=[],
        retrieved_context=[],
        merged_context=[],
        memory_context=[],
        rag_results=[],
        chat_history=[],
        input_budget=500,
    )

    assert set(result["contexts"]) == {
        "user_question",
        "report_context",
        "evidence",
        "retrieved_context",
        "merged_context",
        "memory_context",
        "rag_results",
        "chat_history",
    }
