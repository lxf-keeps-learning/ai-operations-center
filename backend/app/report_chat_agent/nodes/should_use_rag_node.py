"""判断本轮用户问题是否需要调用 RAG 补充知识依据。

职责边界（Sprint6.1）：
  只判断"是否需要 RAG"，不构造 query，不调用 RAG，不生成回答。

运行时机：紧接在 RetrieveReportEvidenceNode 之后。

决策架构（四层）：
  Layer 1 — Hard Guardrail：强制拦截，LLM 不可覆盖。
  Layer 2 — Rule Based：关键词匹配基线。
  Layer 3 — LLM Decision：配置开启时调用（rag_use_llm_decision=True）。
  Layer 4 — Finalize：校验、置信度检查、fallback。
"""

import json
from pathlib import Path

from app.config.settings import settings
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult, llm_client

# ── Intent 分类与关键词映射 ─────────────────────────────

_INTENT_KEYWORD_GROUPS: list[tuple[list[str], str, list[str]]] = [
    (
        [
            "制度", "规范", "标准", "条例", "规定", "规程", "规章", "法规",
            "规则", "判定", "判断规则", "判定规则", "要求", "指南", "办法",
            "有什么依据", "是否合规", "是否合法", "依据什么",
        ],
        "policy_lookup",
        ["制度", "标准"],
    ),
    (
        [
            "案例", "经验", "历史", "惯例", "以往", "以前", "以往案例",
            "类似问题", "类似情况", "有没有先例",
        ],
        "case_lookup",
        ["案例"],
    ),
    (
        [
            "处置", "整改", "流程", "怎么处理", "如何应对", "怎么办",
        ],
        "process_lookup",
        ["制度", "标准", "案例"],
    ),
]

_VALID_INTENTS_NEED_RAG = {"policy_lookup", "case_lookup", "process_lookup", "evidence_insufficient"}
_VALID_INTENTS_NO_RAG = {"tool_query", "report_internal_scope", "none"}
_VALID_INTENTS = _VALID_INTENTS_NEED_RAG | _VALID_INTENTS_NO_RAG
_VALID_SUGGESTED_DOC_TYPES = {"制度", "规范", "标准", "案例", "经验", "流程", "指南", "预案"}

_TOOL_CENTER_QUERY_KEYWORDS = [
    "最近7天", "近7天", "近30天", "近一周", "近一月",
    "当前状态", "实时", "现在", "目前",
    "趋势", "统计", "持续", "对比", "同比", "环比",
    "本周", "本月", "上周", "上月", "去年",
]

_SCENE_LABELS = {
    "essential_safety": "本质安全场景",
    "equipment_maintenance": "设备运维场景",
    "business_improvement": "经营改善场景",
    "capability_enhancement": "能力提升场景",
}

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _first_item_title(item: dict, key_aliases: list[str]) -> str:
    """提取报告条目的业务名称，供 decision/rewrite 保持同一批锚点。"""
    for key in key_aliases:
        value = item.get(key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_required_anchors(state: ReportChatState) -> list[str]:
    """从当前报告中提取最小业务锚点，避免 LLM 只给抽象文档类型。"""
    anchors: list[str] = []
    scene_label = _SCENE_LABELS.get(state.get("scene", ""), "")
    if scene_label:
        anchors.append(scene_label)

    item_sources = [
        ("abnormal_items", ["title", "metric_name", "name", "abnormal_name"]),
        ("risk_items", ["title", "risk_name", "name"]),
        ("advice_items", ["title", "advice", "action", "content", "name"]),
    ]
    for field, aliases in item_sources:
        for item in state.get(field, [])[:2]:
            if not isinstance(item, dict):
                continue
            title = _first_item_title(item, aliases)
            if title and title not in anchors:
                anchors.append(title)

    return anchors


def _is_tool_center_data_question(state: ReportChatState, question: str) -> bool:
    """识别实时数据/趋势统计类问题。

    这类问题需要 Tool Center 或报表数据能力，不应在默认规则路径误调 RAG。
    """
    has_tool_signal = state.get("need_tool_query", False) or any(
        keyword in question for keyword in _TOOL_CENTER_QUERY_KEYWORDS
    )
    if not has_tool_signal:
        return False
    return any(keyword in question for keyword in _TOOL_CENTER_QUERY_KEYWORDS)


# ── Layer 1: Hard Guardrail ─────────────────────────────

def _hard_guardrail_decision(state: ReportChatState) -> ReportChatState | None:
    """强制拦截层。

    满足任一条件立即返回 need_rag=False，LLM 不可覆盖。
    无拦截时返回 None，继续后续决策。
    """
    question = state.get("user_question", "").strip()
    scope = state.get("question_scope", "report_internal")

    if not question:
        state["need_rag"] = False
        state["rag_reason"] = "用户问题为空，不需要查询知识库。"
        state["rag_intent"] = "none"
        state["rag_confidence"] = 1.0
        state["rag_decision_source"] = "guardrail"
        state["suggested_doc_types"] = []
        state["required_anchors"] = []
        return state

    if scope == "out_of_scope":
        state["need_rag"] = False
        state["rag_reason"] = "用户问题与当前报告无关，不需要查询知识库。"
        state["rag_intent"] = "none"
        state["rag_confidence"] = 1.0
        state["rag_decision_source"] = "guardrail"
        state["suggested_doc_types"] = []
        state["required_anchors"] = []
        return state

    if scope == "ioc_global":
        state["need_rag"] = False
        state["rag_reason"] = "当前报告会话不支持全局分析问题的知识库补充。"
        state["rag_intent"] = "none"
        state["rag_confidence"] = 1.0
        state["rag_decision_source"] = "guardrail"
        state["suggested_doc_types"] = []
        state["required_anchors"] = []
        return state

    if not state.get("report_id"):
        state["need_rag"] = False
        state["rag_reason"] = "报告 ID 缺失，无法确定查询范围。"
        state["rag_intent"] = "none"
        state["rag_confidence"] = 1.0
        state["rag_decision_source"] = "guardrail"
        state["suggested_doc_types"] = []
        state["required_anchors"] = []
        return state

    return None


# ── Layer 2: Rule Based Decision ───────────────────────

def _rule_based_decision(state: ReportChatState) -> dict:
    """纯规则判断基线，始终返回有效决策。

    Returns:
        need_rag, reason, intent, confidence, suggested_doc_types, required_anchors.
    """
    question = state.get("user_question", "").strip().lower()
    scope = state.get("question_scope", "report_internal")
    retrieved = state.get("retrieved_context", [])
    evidence_refs = state.get("evidence_refs", [])
    has_report_evidence = bool(retrieved) or bool(evidence_refs)
    required_anchors = _extract_required_anchors(state)

    # 关键词匹配 → 确定意图和文档类型。
    for keywords, intent, doc_types in _INTENT_KEYWORD_GROUPS:
        for kw in keywords:
            if kw in question:
                return {
                    "need_rag": True,
                    "reason": f"用户问题包含关键词'{kw}'，需要知识库中的制度、标准、案例或经验补充依据。",
                    "intent": intent,
                    "confidence": 0.8,
                    "suggested_doc_types": list(doc_types),
                    "required_anchors": required_anchors,
                }

    # 实时状态、趋势、统计类问题优先交给 Tool Center，RAG 不负责查实时业务数据。
    if _is_tool_center_data_question(state, question):
        return {
            "need_rag": False,
            "reason": "用户问题属于实时业务数据、趋势或统计查询，应由 Tool Center 处理，不调用 RAG。",
            "intent": "tool_query",
            "confidence": 0.85,
            "suggested_doc_types": [],
            "required_anchors": required_anchors,
        }

    # report_related 扩展类问题。
    if scope == "report_related":
        return {
            "need_rag": True,
            "reason": "用户问题属于当前报告相关扩展信息，需要查询知识库补充依据。",
            "intent": "evidence_insufficient",
            "confidence": 0.7,
            "suggested_doc_types": ["制度", "标准", "案例"],
            "required_anchors": required_anchors,
        }

    # evidence 不足。
    if not has_report_evidence:
        return {
            "need_rag": True,
            "reason": "当前报告未提供足够依据，需要查询知识库获取相关信息。",
            "intent": "evidence_insufficient",
            "confidence": 0.7,
            "suggested_doc_types": ["制度", "标准", "案例"],
            "required_anchors": required_anchors,
        }

    # 默认：报告内已有足够依据。
    return {
        "need_rag": False,
        "reason": "当前报告已有足够依据，无需额外知识库补充。",
        "intent": "report_internal_scope",
        "confidence": 0.9,
        "suggested_doc_types": [],
        "required_anchors": required_anchors,
    }


# ── Layer 3: LLM Decision ──────────────────────────────

def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _format_decision_prompt(state: ReportChatState) -> str:
    template = _load_prompt("rag_decision.md")
    if not template:
        return ""
    return (template
        .replace("{user_question}", state.get("user_question", ""))
        .replace("{question_scope}", state.get("question_scope", "report_internal"))
        .replace("{report_context}", json.dumps(state.get("report_context", {}), ensure_ascii=False, indent=2))
        .replace("{abnormal_items}", json.dumps(state.get("abnormal_items", []), ensure_ascii=False, indent=2))
        .replace("{risk_items}", json.dumps(state.get("risk_items", []), ensure_ascii=False, indent=2))
        .replace("{retrieved_context}", json.dumps(state.get("retrieved_context", []), ensure_ascii=False, indent=2))
        .replace("{evidence_refs}", json.dumps(state.get("evidence_refs", []), ensure_ascii=False, indent=2))
    )


def _llm_decision(state: ReportChatState, rule_decision: dict) -> dict | None:
    """调用 LLM 进行 RAG 需求分类。

    Returns:
        LLM 决策 dict，或 None（调用失败 / 输出非法）。
    """
    prompt = _format_decision_prompt(state)
    if not prompt:
        return None

    try:
        result: LlmResult = llm_client.chat(
            prompt_content=None,
            user_message=prompt,
            timeout_seconds=settings.operation_llm_timeout_seconds,
        )
    except Exception:
        return None

    if not result.success:
        return None

    content = result.content.strip()
    if not content:
        return None

    return _parse_llm_decision(content)


def _parse_llm_decision(content: str) -> dict | None:
    """异常安全地解析 LLM 返回的 JSON。"""
    # 提取 ```json ... ``` 代码块中的 JSON。
    if "```" in content:
        start = content.find("```json")
        if start == -1:
            start = content.find("```")
        if start != -1:
            first_newline = content.find("\n", start)
            if first_newline != -1:
                end = content.find("```", first_newline + 1)
                if end != -1:
                    content = content[first_newline + 1:end].strip()

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    need_rag = data.get("need_rag")
    if not isinstance(need_rag, bool):
        return None

    intent = data.get("intent", "")
    if not isinstance(intent, str) or intent not in _VALID_INTENTS:
        return None

    # intent 与 need_rag 一致性校验。
    if need_rag and intent not in _VALID_INTENTS_NEED_RAG:
        return None
    if not need_rag and intent not in _VALID_INTENTS_NO_RAG:
        return None

    confidence = data.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(1.0, float(confidence)))

    reason = data.get("reason", "")
    if not isinstance(reason, str):
        reason = ""

    suggested_doc_types = data.get("suggested_doc_types", [])
    if not isinstance(suggested_doc_types, list):
        suggested_doc_types = []
    suggested_doc_types = [
        item.strip()
        for item in suggested_doc_types
        if isinstance(item, str) and item.strip() in _VALID_SUGGESTED_DOC_TYPES
    ]

    required_anchors = data.get("required_anchors", [])
    if not isinstance(required_anchors, list):
        required_anchors = []
    required_anchors = [
        item.strip()
        for item in required_anchors
        if isinstance(item, str) and item.strip()
    ]

    return {
        "need_rag": need_rag,
        "intent": intent,
        "reason": reason,
        "confidence": confidence,
        "suggested_doc_types": suggested_doc_types,
        "required_anchors": required_anchors,
    }


# ── Layer 4: Finalize ──────────────────────────────────

def _finalize_decision(
    state: ReportChatState,
    rule_decision: dict,
    llm_decision: dict | None,
    llm_attempted: bool = False,
) -> ReportChatState:
    """融合规则判断与 LLM 判断，写入最终 State。

    优先级：
      1. LLM 可用、输出合法、置信度达标 → 使用 LLM 决策（source=llm）。
      2. LLM 未启用 → 使用规则决策（source=rule）。
      3. LLM 启用但无法使用 → 使用规则决策（source=fallback）。
    """
    if llm_decision is not None:
        llm_decision = _complete_llm_anchors(state, llm_decision)

    if llm_decision is not None and _accept_llm_decision(llm_decision):
        state["need_rag"] = llm_decision["need_rag"]
        state["rag_reason"] = llm_decision["reason"]
        state["rag_intent"] = llm_decision["intent"]
        state["rag_confidence"] = llm_decision["confidence"]
        state["rag_decision_source"] = "llm"
        state["suggested_doc_types"] = llm_decision["suggested_doc_types"]
        state["required_anchors"] = llm_decision["required_anchors"]
    else:
        source = "fallback" if llm_attempted else "rule"
        state["need_rag"] = rule_decision["need_rag"]
        state["rag_reason"] = rule_decision["reason"]
        state["rag_intent"] = rule_decision["intent"]
        state["rag_confidence"] = rule_decision["confidence"]
        state["rag_decision_source"] = source
        state["suggested_doc_types"] = rule_decision["suggested_doc_types"]
        state["required_anchors"] = rule_decision["required_anchors"]

    return state


def _accept_llm_decision(llm_decision: dict) -> bool:
    """系统校验：判断 LLM 输出是否可被采纳。"""
    confidence = llm_decision["confidence"]

    # 置信度门槛。
    if confidence < settings.rag_decision_confidence_threshold:
        return False

    # need_rag=true 时必须有业务锚点。
    if llm_decision["need_rag"]:
        if not llm_decision.get("required_anchors"):
            return False

    return True


def _complete_llm_anchors(state: ReportChatState, llm_decision: dict) -> dict:
    """LLM 漏填 required_anchors 时，用系统抽取的报告锚点补齐。

    suggested_doc_types 只是文档范围，不是业务锚点；need_rag=true 时仍要
    能落回当前报告的场景、异常项、风险项或建议项，才能进入 RAG。
    """
    if not llm_decision.get("need_rag") or llm_decision.get("required_anchors"):
        return llm_decision

    anchors = _extract_required_anchors(state)
    if not anchors:
        return llm_decision

    completed = dict(llm_decision)
    completed["required_anchors"] = anchors
    return completed


# ── Main Entry ──────────────────────────────────────────

def should_use_rag_node(state: ReportChatState) -> ReportChatState:
    """判断本轮用户问题是否需要调用 RAG 补充知识依据。

    Sprint6.1 升级为四层决策架构：
      1. Hard Guardrail — 强制拦截，LLM 不可覆盖。
      2. Rule Based — 关键词匹配基线（始终计算）。
      3. LLM Decision — 配置开启时调用（rag_use_llm_decision=True）。
      4. Finalize — 系统校验 + 置信度检查 + fallback。

    Args:
        state: 包含 question_scope、user_question 等的 State。

    Returns:
        更新了 need_rag、rag_reason 及 Sprint6.1 决策字段的 State。
    """
    # Layer 1: Hard Guardrail（前置拦截，LLM 不参与）。
    guardrail_result = _hard_guardrail_decision(state)
    if guardrail_result is not None:
        return guardrail_result

    # Layer 2: Rule Based Decision（基线，始终计算）。
    rule_decision = _rule_based_decision(state)

    # Layer 3: LLM Decision（仅配置开启时）。
    llm_decision = None
    llm_attempted = False
    if settings.rag_use_llm_decision:
        llm_attempted = True
        llm_decision = _llm_decision(state, rule_decision)

    # Layer 4: Finalize。
    return _finalize_decision(state, rule_decision, llm_decision, llm_attempted=llm_attempted)
