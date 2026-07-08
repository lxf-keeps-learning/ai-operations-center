"""ShouldUseRagNode 单元测试。

Sprint6 测试重点（规则路径）：
  1. 制度/规范/标准类问题 → need_rag = True。
  2. 案例/经验/历史类问题 → need_rag = True。
  3. 处置/整改/流程类问题 → need_rag = True。
  4. 报告 evidence 不足时 → need_rag = True。
  5. 报告内已有明确答案 → need_rag = False。
  6. out_of_scope 无关问题 → need_rag = False。
  7. ioc_global 无锚点问题 → need_rag = False。
  8. 空问题 → need_rag = False。

Sprint6.1 新增测试重点（LLM 决策路径）：
  9.  guardrail 在 LLM 之前拦截 out_of_scope / ioc_global。
  10. LLM 返回合法 JSON 时使用 LLM 决策。
  11. LLM 返回非法 JSON 时 fallback 到规则。
  12. LLM confidence 过低时 fallback 到规则。
  13. LLM 缺业务锚点时 fallback 到规则。
  14. 默认配置 rag_use_llm_decision=False 时走规则。
"""

import json

from app.report_chat_agent.nodes.should_use_rag_node import should_use_rag_node
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult


def _base_state(
    question: str,
    *,
    scope: str = "report_internal",
    retrieved_context: list | None = None,
    evidence_refs: list[str] | None = None,
) -> ReportChatState:
    return {
        "trace_id": "trace_test_rag",
        "report_id": "1",
        "session_id": "session_test_rag",
        "user_id": "tester",
        "user_question": question,
        "scene": "essential_safety",
        "report_context": {"summary": "本次报告存在高等级风险。"},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": scope,  # type: ignore[arg-type]
        "scope_reason": "",
        "retrieved_context": retrieved_context or [],
        "evidence_refs": evidence_refs or [],
        "need_rag": False,
        "rag_reason": "",
        "rag_query": {},
        "rag_results": [],
        "rag_source_refs": [],
        "used_rag": False,
        "merged_context": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "llm_usages": [],
        "errors": [],
    }


class TestShouldUseRagNode:
    """ShouldUseRagNode 判断规则测试。"""

    # ── 应触发 RAG 的测试用例 ──────────────────────────

    def test_zhidu_yiju_triggers_rag(self) -> None:
        """用户询问制度依据 → need_rag = True."""
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "制度" in result["rag_reason"]

    def test_biaozhun_triggers_rag(self) -> None:
        """用户询问标准规范 → need_rag = True."""
        state = _base_state("这个判断是否符合国家标准？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "标准" in result["rag_reason"]

    def test_anli_jingyan_triggers_rag(self) -> None:
        """用户询问历史案例 → need_rag = True."""
        state = _base_state("以前有没有类似的案例？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "案例" in result["rag_reason"] or "经验" in result["rag_reason"]

    def test_chuzhi_zhenggai_triggers_rag(self) -> None:
        """用户询问处置要求和整改流程 → need_rag = True."""
        state = _base_state("这种异常一般怎么处理？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "怎么处理" in result["rag_reason"]

    def test_liucheng_wenti_triggers_rag(self) -> None:
        """用户询问工作流程 → need_rag = True."""
        state = _base_state("这个问题的操作规程是什么？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "规程" in result["rag_reason"]

    def test_evidence_buzu_triggers_rag(self) -> None:
        """报告 evidence 为空且 retrieved_context 为空 → need_rag = True."""
        state = _base_state("为什么这个风险排第一？", retrieved_context=[], evidence_refs=[])
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "未提供足够依据" in result["rag_reason"]

    def test_yiwang_anli_triggers_rag(self) -> None:
        """用户询问以前类似问题 → need_rag = True."""
        state = _base_state("以前类似问题怎么整改的？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True

    def test_fagui_yiju_triggers_rag(self) -> None:
        """用户询问法规依据 → need_rag = True."""
        state = _base_state("这个依据什么法规？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True

    def test_benzhi_anquan_rule_question_triggers_rag(self) -> None:
        """用户询问本质安全判断规则 → need_rag = True."""
        state = _base_state("这次能查到本质安全判断的规则不")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert "规则" in result["rag_reason"]

    # ── 不应触发 RAG 的测试用例 ────────────────────────

    def test_report_internal_has_evidence_skips_rag(self) -> None:
        """报告内问题且已有 evidence → need_rag = False."""
        state = _base_state(
            "为什么这个风险排第一？",
            retrieved_context=[{"type": "risk_item", "title": "风险1", "content": "高风险"}],
            evidence_refs=["EV_001"],
        )
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert "足够依据" in result["rag_reason"]

    def test_out_of_scope_skips_rag(self) -> None:
        """无关问题 → need_rag = False."""
        state = _base_state("帮我写首诗", scope="out_of_scope")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert "无关" in result["rag_reason"]

    def test_ioc_global_skips_rag(self) -> None:
        """IOC 全局问题 → need_rag = False."""
        state = _base_state("全公司本月风险趋势如何？", scope="ioc_global")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert "全局分析" in result["rag_reason"]

    def test_empty_question_skips_rag(self) -> None:
        """空问题 → need_rag = False."""
        state = _base_state("")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False

    def test_scope_out_of_scope_with_zhidu_keyword_skips_rag(self) -> None:
        """虽然含"制度"关键词，但 question_scope 已经是 out_of_scope → 不调用 RAG。"""
        state = _base_state("告诉我这个制度规范", scope="out_of_scope")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert "无关" in result["rag_reason"]

    def test_report_related_tool_query_skips_rag_even_with_evidence(self) -> None:
        """实时/趋势类 report_related 问题不应调用 RAG，应交给 Tool Center。"""
        state = _base_state(
            "最近7天这个异常是否持续？",
            scope="report_related",
            retrieved_context=[{"type": "abnormal_item", "content": "超期缺陷"}],
            evidence_refs=["EV_001"],
        )
        state["need_tool_query"] = True
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_intent"] == "tool_query"
        assert "Tool Center" in result["rag_reason"]

    def test_report_related_tool_query_without_evidence_skips_rag(self) -> None:
        """趋势/对比类 report_related 问题无 evidence 时也不能误调 RAG。"""
        state = _base_state(
            "最近7天这个异常是否持续？",
            scope="report_related",
            retrieved_context=[],
            evidence_refs=[],
        )
        state["need_tool_query"] = True
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_intent"] == "tool_query"
        assert "实时业务数据" in result["rag_reason"]


# ── Helper: 构造 mock LlmResult ────────────────────────

def _mock_llm_result(content: str, *, success: bool = True) -> LlmResult:
    return LlmResult(
        content=content,
        model="mock",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_ms=100,
        success=success,
        error_message="",
        system_prompt="",
    )


class TestShouldUseRagNodeLlmDecision:
    """Sprint6.1 LLM 决策路径测试（需启用 rag_use_llm_decision=True）。"""

    # ── Guardrail 优先于 LLM ──────────────────────────

    def test_guardrail_intercepts_out_of_scope_before_llm(self, monkeypatch) -> None:
        """out_of_scope 不走 LLM，guardrail 直接拦截。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({"need_rag": True, "intent": "policy_lookup", "reason": "x", "confidence": 0.95,
                            "suggested_doc_types": ["制度"], "required_anchors": ["安全"]}, ensure_ascii=False),
            ),
        )
        state = _base_state("告诉我这个制度规范", scope="out_of_scope")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_decision_source"] == "guardrail"

    def test_guardrail_intercepts_ioc_global_before_llm(self, monkeypatch) -> None:
        """ioc_global 不走 LLM，guardrail 直接拦截。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({"need_rag": True, "intent": "policy_lookup", "reason": "x", "confidence": 0.95,
                            "suggested_doc_types": ["制度"], "required_anchors": ["趋势"]}, ensure_ascii=False),
            ),
        )
        state = _base_state("全公司本月风险趋势如何？", scope="ioc_global")
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_decision_source"] == "guardrail"

    # ── LLM 返回合法 JSON ─────────────────────────────

    def test_llm_valid_json_uses_llm_decision(self, monkeypatch) -> None:
        """LLM 返回合法 JSON → 使用 LLM 决策，source=llm。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "need_rag": True,
                    "intent": "policy_lookup",
                    "reason": "用户询问制度依据",
                    "confidence": 0.92,
                    "suggested_doc_types": ["制度"],
                    "required_anchors": ["风险等级"],
                }, ensure_ascii=False),
            ),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "llm"
        assert result["rag_intent"] == "policy_lookup"
        assert result["rag_confidence"] == 0.92
        assert result["suggested_doc_types"] == ["制度"]
        assert result["required_anchors"] == ["风险等级"]

    def test_llm_valid_json_no_rag_uses_llm_decision(self, monkeypatch) -> None:
        """LLM 返回 need_rag=false 的合法 JSON → 使用 LLM 决策。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "need_rag": False,
                    "intent": "report_internal_scope",
                    "reason": "报告已包含足够依据",
                    "confidence": 0.88,
                    "suggested_doc_types": [],
                    "required_anchors": [],
                }, ensure_ascii=False),
            ),
        )
        state = _base_state(
            "为什么这个风险排第一？",
            retrieved_context=[{"type": "risk_item", "title": "风险1", "content": "高风险"}],
            evidence_refs=["EV_001"],
        )
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_decision_source"] == "llm"
        assert result["rag_intent"] == "report_internal_scope"

    # ── LLM 非法 JSON → fallback ─────────────────────

    def test_llm_invalid_json_falls_back_to_rule(self, monkeypatch) -> None:
        """LLM 返回非法 JSON → fallback 到规则，source=fallback。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result("这不是 JSON 格式"),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "fallback"
        assert "制度" in result["rag_reason"]

    def test_llm_empty_content_falls_back_to_rule(self, monkeypatch) -> None:
        """LLM 返回空内容 → fallback 到规则。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(""),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "fallback"

    def test_llm_call_failure_falls_back_to_rule(self, monkeypatch) -> None:
        """LLM 调用失败（success=False）→ fallback 到规则。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result("", success=False),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "fallback"

    # ── LLM confidence 过低 → fallback ───────────────

    def test_llm_low_confidence_falls_back_to_rule(self, monkeypatch) -> None:
        """LLM confidence < 0.65 阈值 → fallback 到规则。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "need_rag": True,
                    "intent": "policy_lookup",
                    "reason": "不确定",
                    "confidence": 0.35,
                    "suggested_doc_types": ["制度"],
                    "required_anchors": ["风险"],
                }, ensure_ascii=False),
            ),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "fallback"

    # ── LLM need_rag=true 但缺业务锚点 → fallback ──

    def test_llm_no_anchors_uses_system_anchors(self, monkeypatch) -> None:
        """LLM 漏填 required_anchors 时，系统用报告锚点补齐后可采纳。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.settings.rag_use_llm_decision",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.should_use_rag_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "need_rag": True,
                    "intent": "policy_lookup",
                    "reason": "需要制度",
                    "confidence": 0.85,
                    "suggested_doc_types": [],
                    "required_anchors": [],
                }, ensure_ascii=False),
            ),
        )
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "llm"
        assert result["required_anchors"] == ["本质安全场景"]

    # ── 默认配置（rag_use_llm_decision=False）走规则 ──

    def test_default_config_uses_rule(self) -> None:
        """rag_use_llm_decision=False（默认）→ 走规则路径，source=rule。"""
        state = _base_state("这个判断有没有制度依据？")
        result = should_use_rag_node(state)
        assert result["need_rag"] is True
        assert result["rag_decision_source"] == "rule"

    def test_default_config_report_internal_skips_rag(self) -> None:
        """默认配置下，报告内有 evidence 时走规则判断为不需要 RAG。"""
        state = _base_state(
            "为什么这个风险排第一？",
            retrieved_context=[{"type": "risk_item", "title": "风险1", "content": "高风险"}],
            evidence_refs=["EV_001"],
        )
        result = should_use_rag_node(state)
        assert result["need_rag"] is False
        assert result["rag_decision_source"] == "rule"
