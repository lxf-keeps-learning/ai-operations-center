"""BuildRagQueryNode 单元测试。

Sprint6 测试重点（规则路径）：
  1. query 融合了 report 锚点（异常项、风险项、场景）。
  2. query 不只是复制用户原问题。
  3. doc_type 根据问题类型动态推断。
  4. 缺少锚点时至少带 scene 和用户问题。
  5. 不调用外部 RAG 服务。

Sprint6.1 新增测试重点（LLM Rewrite 路径）：
  6. 默认 rag_use_query_rewrite=False 时走规则。
  7. LLM 返回合法 JSON 时使用 rewritten_query。
  8. LLM 非法 JSON / 空内容 / 调用失败时 fallback。
  9. LLM confidence 过低时 fallback。
  10. LLM query 缺少业务锚点时 fallback。
  11. LLM query 含无边界扩展词时 fallback。
  12. query_rewrite_source 正确写入。
  13. 最终 rag_query 兼容 CallRagNode。
"""

import json

from app.report_chat_agent.nodes.build_rag_query_node import build_rag_query_node
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult


def _state_with_abnormal(
    question: str,
    abnormal_items: list[dict] | None = None,
    risk_items: list[dict] | None = None,
    advice_items: list[dict] | None = None,
    scene: str = "essential_safety",
    report_context: dict | None = None,
) -> ReportChatState:
    return {
        "trace_id": "trace_test_build_rag",
        "report_id": "1",
        "session_id": "session_test",
        "user_id": "tester",
        "user_question": question,
        "scene": scene,
        "report_context": report_context or {"summary": "本次报告存在高等级风险。", "domain": "safety"},
        "report_sections": [],
        "abnormal_items": abnormal_items or [],
        "risk_items": risk_items or [],
        "advice_items": advice_items or [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_rag": True,
        "rag_reason": "需要 RAG",
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


class TestBuildRagQueryNode:
    """BuildRagQueryNode 的查询构造测试。"""

    def test_query_contains_scene_and_anchor(self) -> None:
        """用户问处置问题 → query 包含场景 + 异常项 + 用户意图。"""
        state = _state_with_abnormal(
            question="这种异常一般怎么处理？",
            abnormal_items=[{"title": "超期未处理缺陷", "metric_name": "defect_rate"}],
        )
        result = build_rag_query_node(state)
        rag_query = result["rag_query"]

        assert "本质安全场景" in rag_query["query"]
        assert "超期未处理缺陷" in rag_query["query"]
        assert "怎么处理" in rag_query["query"]
        assert rag_query["scene"] == "essential_safety"
        assert rag_query["top_k"] == 5

    def test_query_not_just_user_question(self) -> None:
        """query 不是简单复制用户问题，而是融合了场景和锚点。"""
        state = _state_with_abnormal(
            question="有什么依据？",
            abnormal_items=[{"title": "设备超期运行", "metric_name": "overdue_rate"}],
        )
        result = build_rag_query_node(state)

        assert "本质安全" in result["rag_query"]["query"]
        assert "设备超期" in result["rag_query"]["query"]
        # query 应比原问题长（融合了锚点）。
        assert len(result["rag_query"]["query"]) > len("有什么依据？")

    def test_doc_type_inferred_for_zhidu(self) -> None:
        """问制度依据 → doc_type 包含 "制度" 和 "标准"。"""
        state = _state_with_abnormal(
            question="这个判断有没有制度依据？",
            abnormal_items=[{"title": "超期未处理缺陷"}],
        )
        result = build_rag_query_node(state)
        filters = result["rag_query"]["filters"]
        assert "制度" in filters["doc_type"]
        assert "标准" in filters["doc_type"]

    def test_doc_type_inferred_for_rule_question(self) -> None:
        """问判断规则 → doc_type 包含 "制度" 和 "标准"。"""
        state = _state_with_abnormal(
            question="这次能查到本质安全判断的规则不",
            abnormal_items=[{"title": "本质安全高风险项"}],
        )
        result = build_rag_query_node(state)
        filters = result["rag_query"]["filters"]
        assert "制度" in filters["doc_type"]
        assert "标准" in filters["doc_type"]

    def test_doc_type_inferred_for_anli(self) -> None:
        """问历史案例 → doc_type 包含 "案例"。"""
        state = _state_with_abnormal(
            question="以前有没有类似案例？",
            abnormal_items=[{"title": "设备超期"}],
        )
        result = build_rag_query_node(state)
        filters = result["rag_query"]["filters"]
        assert filters["doc_type"] == ["案例"]

    def test_doc_type_default_for_general(self) -> None:
        """一般问题 → doc_type 为全部类型。"""
        state = _state_with_abnormal(
            question="为什么这个风险排第一？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        filters = result["rag_query"]["filters"]
        assert len(filters["doc_type"]) == 3

    def test_no_abnormal_items_fallback_to_scene(self) -> None:
        """没有异常项时，query 至少包含场景和用户问题。"""
        state = _state_with_abnormal(
            question="这种情况一般怎么处理？",
            abnormal_items=[],
            risk_items=[],
            advice_items=[],
        )
        result = build_rag_query_node(state)
        query = result["rag_query"]["query"]
        assert "本质安全" in query
        assert "怎么处理" in query
        assert result["rag_query"]["scene"] == "essential_safety"

    def test_risk_item_as_anchor(self) -> None:
        """使用风险项作为锚点。"""
        state = _state_with_abnormal(
            question="这个风险的处理标准是什么？",
            abnormal_items=[],
            risk_items=[{"title": "超期未处理缺陷风险", "risk_name": "overdue_risk"}],
        )
        result = build_rag_query_node(state)
        query = result["rag_query"]["query"]
        assert "本质安全" in query
        assert "超期未处理缺陷风险" in query

    def test_advice_item_as_anchor(self) -> None:
        """只有建议项时，也能作为 RAG query 的业务锚点。"""
        state = _state_with_abnormal(
            question="这个建议动作有没有制度依据？",
            abnormal_items=[],
            risk_items=[],
            advice_items=[{"title": "建立超期缺陷闭环整改机制"}],
        )
        result = build_rag_query_node(state)
        query = result["rag_query"]["query"]
        assert "本质安全" in query
        assert "建立超期缺陷闭环整改机制" in query

    def test_multiple_anchor_items(self) -> None:
        """同时有异常项和风险项时，query 包含两者。"""
        state = _state_with_abnormal(
            question="怎么整改？",
            abnormal_items=[{"title": "设备超期运行"}],
            risk_items=[{"title": "设备超期风险"}],
        )
        result = build_rag_query_node(state)
        query = result["rag_query"]["query"]
        assert "设备超期运行" in query
        assert "设备超期风险" in query

    def test_diff_scene_label(self) -> None:
        """不同场景对应不同前缀。"""
        state = _state_with_abnormal(
            question="这个异常怎么处理？",
            abnormal_items=[{"title": "设备故障率"}],
            scene="equipment_maintenance",
        )
        result = build_rag_query_node(state)
        assert "设备运维场景" in result["rag_query"]["query"]

    def test_filters_include_scene_and_permission(self) -> None:
        """filters 始终包含 scene 和 permission_scope。"""
        state = _state_with_abnormal(
            question="有什么处置规定？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        filters = result["rag_query"]["filters"]
        assert filters["permission_scope"] == "current_user_allowed"
        assert filters["scene"] == "essential_safety"

    def test_does_not_use_rag_service(self) -> None:
        """不调用外部 RAG 服务，只设置 rag_query。"""
        state = _state_with_abnormal(
            question="这个风险有没有制度依据？",
            risk_items=[{"title": "高风险项"}],
        )
        result = build_rag_query_node(state)
        assert "rag_query" in result
        assert result["rag_query"]["query"]
        # 确认没有调用结果字段。
        assert result.get("rag_results") == []
        assert result.get("rag_source_refs") == []

    def test_top_k_always_5(self) -> None:
        """top_k 第一版固定为 5。"""
        state = _state_with_abnormal(
            question="这个依据什么法规？",
            abnormal_items=[{"title": "缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["rag_query"]["top_k"] == 5


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


def _state_for_rewrite(
    question: str,
    abnormal_items: list[dict] | None = None,
    risk_items: list[dict] | None = None,
    report_context: dict | None = None,
    scene: str = "essential_safety",
    rag_intent: str = "policy_lookup",
    suggested_doc_types: list[str] | None = None,
) -> ReportChatState:
    state = _state_with_abnormal(
        question=question,
        abnormal_items=abnormal_items,
        risk_items=risk_items,
        report_context=report_context,
        scene=scene,
    )
    state["rag_intent"] = rag_intent
    state["suggested_doc_types"] = suggested_doc_types or ["制度", "标准"]
    return state


class TestBuildRagQueryNodeRewrite:
    """Sprint6.1 LLM Query Rewrite 路径测试。"""

    # ── 默认配置走规则 ────────────────────────────────

    def test_default_config_uses_rule_query(self) -> None:
        """rag_use_query_rewrite=False（默认）→ 规则路径，source=rule。"""
        state = _state_for_rewrite(
            "这个判断有没有制度依据？",
            abnormal_items=[{"title": "超期未处理缺陷"}],
        )
        result = build_rag_query_node(state)
        assert "本质安全场景" in result["rag_query"]["query"]
        assert result["query_rewrite_source"] == "rule"

    # ── LLM 返回合法 JSON ─────────────────────────────

    def test_llm_valid_rewrite_uses_llm(self, monkeypatch) -> None:
        """LLM 返回合法 rewrite JSON → source=llm，rag_query 使用改写 query。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "本质安全场景下，超期未处理缺陷的制度依据和处置要求",
                    "query_keywords": ["超期未处理缺陷", "制度依据", "处置要求"],
                    "doc_types": ["制度", "标准"],
                    "reason": "替换指代并融合场景锚点",
                    "confidence": 0.92,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个有没有制度依据？",
            abnormal_items=[{"title": "超期未处理缺陷"}],
        )
        result = build_rag_query_node(state)

        assert result["query_rewrite_source"] == "llm"
        assert result["rewritten_query"] == "本质安全场景下，超期未处理缺陷的制度依据和处置要求"
        assert "超期未处理缺陷" in result["rag_query"]["query"]
        assert result["rag_query"]["top_k"] == 5
        assert "制度" in result["rag_query"]["filters"]["doc_type"]

    def test_llm_rewrite_no_rag_intent_from_decision(self, monkeypatch) -> None:
        """LLM rewrite 使用 ShouldUseRagNode 的 intent 和 suggested_doc_types。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "设备运维场景下，设备超期运行的案例和经验",
                    "query_keywords": ["设备超期运行", "案例", "经验"],
                    "doc_types": ["案例", "经验"],
                    "reason": "用户询问历史案例",
                    "confidence": 0.90,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "以前有没有类似案例？",
            abnormal_items=[{"title": "设备超期运行"}],
            scene="equipment_maintenance",
            rag_intent="case_lookup",
            suggested_doc_types=["案例"],
        )
        result = build_rag_query_node(state)

        assert result["query_rewrite_source"] == "llm"
        assert "设备运维场景" in result["rag_query"]["query"]
        assert result["rag_query"]["filters"]["scene"] == "equipment_maintenance"

    def test_llm_rewrite_accepts_required_anchors_from_decision(self, monkeypatch) -> None:
        """Rewrite 校验会使用 ShouldUseRagNode 写入的 required_anchors。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "高频报警整改建议的制度依据",
                    "query_keywords": ["高频报警整改建议", "制度依据"],
                    "doc_types": ["制度"],
                    "reason": "使用上游 required_anchors 约束改写",
                    "confidence": 0.90,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个建议有没有制度依据？",
            abnormal_items=[],
            risk_items=[],
        )
        state["required_anchors"] = ["高频报警整改建议"]
        result = build_rag_query_node(state)

        assert result["query_rewrite_source"] == "llm"
        assert "高频报警整改建议" in result["rag_query"]["query"]

    # ── LLM 非法 JSON / 空 / 失败 → fallback ────────

    def test_llm_invalid_json_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result("这不是 JSON"),
        )
        state = _state_for_rewrite(
            "这个有没有制度依据？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"
        assert "本质安全" in result["rag_query"]["query"]

    def test_llm_empty_content_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(""),
        )
        state = _state_for_rewrite(
            "这个有没有制度依据？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"

    def test_llm_call_failure_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result("", success=False),
        )
        state = _state_for_rewrite(
            "这个有没有制度依据？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"

    # ── LLM confidence 过低 → fallback ───────────────

    def test_llm_low_confidence_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "本质安全场景下，超期缺陷处置要求",
                    "query_keywords": ["超期缺陷", "处置要求"],
                    "doc_types": ["制度", "标准"],
                    "reason": "测试",
                    "confidence": 0.35,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个怎么处理？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"
        assert result["query_rewrite_confidence"] == 0.0  # 未使用 LLM

    # ── LLM query 缺少业务锚点 → fallback ─────────────

    def test_llm_query_missing_anchors_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "请告诉我相关的制度和标准",
                    "query_keywords": ["制度", "标准"],
                    "doc_types": ["制度", "标准"],
                    "reason": "用户询问制度",
                    "confidence": 0.85,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个有没有制度依据？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"
        # rule fallback 仍包含锚点。
        assert "超期缺陷" in result["rag_query"]["query"]

    # ── LLM query 含无边界扩展词 → fallback ──────────

    def test_llm_query_boundary_word_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "全公司范围内超期缺陷的处置制度",
                    "query_keywords": ["超期缺陷", "处置制度"],
                    "doc_types": ["制度", "标准"],
                    "reason": "测试",
                    "confidence": 0.85,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个怎么处理？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"

    # ── LLM query == user_question → fallback ────────

    def test_llm_query_equals_user_question_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "这个怎么处理",
                    "query_keywords": ["怎么处理"],
                    "doc_types": ["制度", "标准"],
                    "reason": "未改写",
                    "confidence": 0.90,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个怎么处理",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        assert result["query_rewrite_source"] == "fallback"

    # ── doc_type 非白名单 → 清洗 ─────────────────────

    def test_llm_invalid_doc_type_cleaned(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "本质安全场景下，超期缺陷的处置制度和规范",
                    "query_keywords": ["超期缺陷", "处置制度"],
                    "doc_types": ["制度", "标准", "invalid_type", "another_bad"],
                    "reason": "测试",
                    "confidence": 0.88,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这个怎么处理？",
            abnormal_items=[{"title": "超期缺陷"}],
        )
        result = build_rag_query_node(state)
        # 清洗后只保留白名单内的类型。
        doc_types = result["rag_query"]["filters"]["doc_type"]
        assert "制度" in doc_types
        assert "标准" in doc_types
        assert "invalid_type" not in doc_types
        assert result["query_rewrite_source"] == "llm"

    # ── 兼容 CallRagNode 的结构验证 ──────────────────

    def test_rag_query_compatible_with_call_rag_node(self, monkeypatch) -> None:
        """无论走规则还是 LLM，rag_query 结构兼容 CallRagNode。"""
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.settings.rag_use_query_rewrite",
            True,
        )
        monkeypatch.setattr(
            "app.report_chat_agent.nodes.build_rag_query_node.llm_client.chat",
            lambda *a, **kw: _mock_llm_result(
                json.dumps({
                    "query": "本质安全场景下，超期未处理缺陷的处置要求和整改流程",
                    "query_keywords": ["超期未处理缺陷", "处置要求", "整改流程"],
                    "doc_types": ["制度", "标准"],
                    "reason": "替换指代并融合场景和异常项锚点",
                    "confidence": 0.91,
                }, ensure_ascii=False),
            ),
        )
        state = _state_for_rewrite(
            "这种异常一般怎么处理？",
            abnormal_items=[{"title": "超期未处理缺陷"}],
        )
        result = build_rag_query_node(state)

        rag_query = result["rag_query"]
        # CallRagNode 依赖的结构字段。
        assert "query" in rag_query
        assert "scene" in rag_query
        assert "top_k" in rag_query
        assert "filters" in rag_query
        assert "doc_type" in rag_query["filters"]
        assert "permission_scope" in rag_query["filters"]
        assert rag_query["top_k"] == 5

        # LLM 路径也写入 Sprint6.1 字段。
        assert result["query_rewrite_source"] == "llm"
        assert result["rewritten_query"]
        assert len(result["query_keywords"]) == 3
