"""基于用户问题和当前报告锚点构造 RAG 查询请求。

职责边界（Sprint6.1）：
  只构造 rag_query，不调用 RAG，不生成回答。

运行时机：紧接在 ShouldUseRagNode 之后，此时 State 中已有：
  - need_rag=True（已确认需要 RAG）
  - user_question、report_context、abnormal_items、risk_items、advice_items
  - scene、rag_intent、suggested_doc_types（LLM 决策启用时）

核心设计原则：
  1. query 不能只复制用户原问题，必须融合报告业务锚点。
  2. 锚点包括 scene、abnormal_item、risk_item、advice_item、metric_name 等。
  3. 默认走规则拼接；rag_use_query_rewrite=True 时启用 LLM 改写。
  4. LLM 改写失败时有完整 fallback 链。
  5. top_k 第一版固定为 5。
"""

import json
from pathlib import Path

from app.config.settings import settings
from app.rag.schemas import RagSearchFilters, RagSearchRequest
from app.report_chat_agent.state import ReportChatState
from app.runtime.llm.client import LlmResult, llm_client

# ── 文档类型推断（规则路径用） ─────────────────────────

_DOC_TYPE_MAP: list[tuple[list[str], list[str]]] = [
    (["制度", "规范", "规定", "规章", "法规", "条例", "规则", "指南", "办法"], ["制度", "标准"]),
    (["标准", "国标", "行标"], ["标准"]),
    (["案例", "经验", "历史", "惯例", "先例"], ["案例"]),
    (["处置", "整改", "流程", "怎么处理", "如何应对", "怎么办"], ["制度", "标准", "案例"]),
]

_VALID_DOC_TYPES = {"制度", "规范", "标准", "案例", "经验", "流程", "指南", "预案"}
_BOUNDARY_BLACKLIST = ["全公司", "全部", "所有业务域", "全量扫描", "所有时间", "全范围"]

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


# ── 工具函数 ───────────────────────────────────────────

def _infer_doc_types(question: str) -> list[str]:
    q = question.lower()
    for keywords, doc_types in _DOC_TYPE_MAP:
        if any(kw in q for kw in keywords):
            return doc_types
    return ["制度", "标准", "案例"]


def _first_item_title(items: list[dict], key_aliases: list[str]) -> str:
    if not items:
        return ""
    item = items[0]
    for key in key_aliases:
        val = item.get(key, "")
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return str(item.get(list(item.keys())[0], "")) if item else ""


def _build_anchor_description(
    abnormal_items: list[dict],
    risk_items: list[dict],
    advice_items: list[dict],
) -> str:
    parts: list[str] = []

    abnormal = _first_item_title(abnormal_items, ["title", "metric_name", "name", "abnormal_name"])
    if abnormal:
        parts.append(abnormal)

    risk = _first_item_title(risk_items, ["title", "risk_name", "name"])
    if risk and risk not in parts:
        parts.append(risk)

    advice = _first_item_title(advice_items, ["title", "advice", "action", "content", "name"])
    if advice and advice not in parts:
        parts.append(advice)

    if not parts:
        return ""

    if len(parts) == 1:
        return parts[0]
    return "、".join(parts[:-1]) + "和" + parts[-1]


def _build_query_text(
    user_question: str,
    scene: str,
    anchor_desc: str,
) -> str:
    scene_label = _scene_label(scene)
    parts: list[str] = []

    if scene_label:
        parts.append(scene_label)

    if anchor_desc:
        parts.append(anchor_desc)

    intent = user_question.strip().rstrip("？?。.!！")
    if intent:
        intent_short = intent[:30]
        parts.append(intent_short)

    return "，".join(parts)


def _scene_label(scene: str) -> str:
    mapping = {
        "essential_safety": "本质安全场景",
        "equipment_maintenance": "设备运维场景",
        "business_improvement": "经营改善场景",
        "capability_enhancement": "能力提升场景",
    }
    return mapping.get(scene, scene)


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ── Layer 1: 业务锚点提取 ──────────────────────────────

def _extract_business_anchors(state: ReportChatState) -> dict:
    """从 State 中提取业务锚点信息。

    Returns:
        scene, scene_label, anchor_desc, anchor_titles, has_anchors.
    """
    scene = state.get("scene", "essential_safety")
    scene_label = _scene_label(scene)
    abnormal_items = state.get("abnormal_items", [])
    risk_items = state.get("risk_items", [])
    advice_items = state.get("advice_items", [])

    anchor_desc = _build_anchor_description(abnormal_items, risk_items, advice_items)

    anchor_titles: list[str] = []
    for item in abnormal_items[:2]:
        title = _first_item_title([item], ["title", "metric_name", "name", "abnormal_name"])
        if title and title not in anchor_titles:
            anchor_titles.append(title)
    for item in risk_items[:2]:
        title = _first_item_title([item], ["title", "risk_name", "name"])
        if title and title not in anchor_titles:
            anchor_titles.append(title)
    for item in advice_items[:2]:
        title = _first_item_title([item], ["title", "advice", "action", "content", "name"])
        if title and title not in anchor_titles:
            anchor_titles.append(title)
    for title in state.get("required_anchors", []):
        if isinstance(title, str) and title.strip() and title.strip() not in anchor_titles:
            anchor_titles.append(title.strip())

    return {
        "scene": scene,
        "scene_label": scene_label,
        "anchor_desc": anchor_desc,
        "anchor_titles": anchor_titles,
        "has_anchors": bool(anchor_titles),
    }


# ── Layer 2: 规则 Query 构造 ───────────────────────────

def _build_rule_query(state: ReportChatState, anchors: dict) -> RagSearchRequest:
    """基于规则构造 RAG 查询请求。

    保持 Sprint6 原有能力不变：
      - scene + anchor_desc + user_intent 拼接。
      - 关键词推断 doc_type。
      - top_k=5。
    """
    user_question = state.get("user_question", "")
    scene = anchors["scene"]
    anchor_desc = anchors["anchor_desc"]

    query_text = _build_query_text(user_question, scene, anchor_desc)
    doc_types = _infer_doc_types(user_question)

    return RagSearchRequest(
        query=query_text,
        scene=scene,
        top_k=5,
        filters=RagSearchFilters(
            doc_type=doc_types,
            permission_scope="current_user_allowed",
            scene=scene if scene else None,
        ),
    )


# ── Layer 3: LLM Query Rewrite ─────────────────────────

def _format_rewrite_prompt(state: ReportChatState, anchors: dict) -> str:
    template = _load_prompt("rag_query_rewrite.md")
    if not template:
        return ""
    return (template
        .replace("{user_question}", state.get("user_question", ""))
        .replace("{rag_intent}", state.get("rag_intent", ""))
        .replace("{suggested_doc_types}", json.dumps(state.get("suggested_doc_types", []), ensure_ascii=False))
        .replace("{required_anchors}", json.dumps(state.get("required_anchors", []), ensure_ascii=False))
        .replace("{report_context}", json.dumps(state.get("report_context", {}), ensure_ascii=False, indent=2))
        .replace("{abnormal_items}", json.dumps(state.get("abnormal_items", []), ensure_ascii=False, indent=2))
        .replace("{risk_items}", json.dumps(state.get("risk_items", []), ensure_ascii=False, indent=2))
        .replace("{advice_items}", json.dumps(state.get("advice_items", []), ensure_ascii=False, indent=2))
        .replace("{retrieved_context}", json.dumps(state.get("retrieved_context", []), ensure_ascii=False, indent=2))
        .replace("{scene}", anchors.get("scene_label") or state.get("scene", ""))
    )


def _llm_rewrite_query(state: ReportChatState, anchors: dict) -> dict | None:
    """调用 LLM 改写 RAG 检索 query。

    Returns:
        改写结果 dict，或 None（调用失败 / 解析失败）。
    """
    prompt = _format_rewrite_prompt(state, anchors)
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

    return _parse_llm_rewrite(content)


def _parse_llm_rewrite(content: str) -> dict | None:
    """异常安全地解析 LLM 返回的 JSON。"""
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

    query = data.get("query", "")
    if not isinstance(query, str) or not query.strip():
        return None

    query_keywords = data.get("query_keywords", [])
    if not isinstance(query_keywords, list):
        query_keywords = []

    doc_types = data.get("doc_types", [])
    if not isinstance(doc_types, list):
        doc_types = []

    reason = data.get("reason", "")
    if not isinstance(reason, str):
        reason = ""

    confidence = data.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "query": query.strip(),
        "query_keywords": [str(k) for k in query_keywords if isinstance(k, str)],
        "doc_types": [str(d) for d in doc_types if isinstance(d, str)],
        "reason": reason,
        "confidence": confidence,
    }


# ── Layer 4: Query 校验 ────────────────────────────────

def _validate_rewritten_query(rewrite_result: dict, anchors: dict) -> bool:
    """校验 LLM 改写结果，并在原地清洗 doc_types。

    Returns:
        True 表示通过校验。
    """
    query = rewrite_result.get("query", "").strip()
    if not query:
        return False

    # 必须包含场景标签或至少一个业务锚点。
    scene_label = anchors.get("scene_label", "")
    anchor_titles = anchors.get("anchor_titles", [])
    has_scene = bool(scene_label and scene_label in query)
    has_anchor = any(a and a in query for a in anchor_titles)
    if not has_scene and not has_anchor:
        return False

    # 禁止无边界扩展词。
    for word in _BOUNDARY_BLACKLIST:
        if word in query:
            return False

    # 清洗 doc_types 至白名单。
    raw_doc_types = rewrite_result.get("doc_types", [])
    cleaned = [d for d in raw_doc_types if d in _VALID_DOC_TYPES]
    rewrite_result["doc_types"] = cleaned if cleaned else ["制度", "标准", "案例"]

    return True


# ── Layer 5: 决策融合 ──────────────────────────────────

def _build_rag_request(query_text: str, doc_types: list[str], scene: str) -> dict:
    return RagSearchRequest(
        query=query_text,
        scene=scene,
        top_k=5,
        filters=RagSearchFilters(
            doc_type=doc_types or ["制度", "标准", "案例"],
            permission_scope="current_user_allowed",
            scene=scene if scene else None,
        ),
    ).model_dump()


def _accept_rewrite(
    rewrite_result: dict,
    state: ReportChatState,
    anchors: dict,
) -> bool:
    """判断 LLM 改写结果是否可被采纳。"""
    # 置信度门槛。
    confidence = rewrite_result.get("confidence", 0.0)
    if confidence < settings.rag_query_rewrite_confidence_threshold:
        return False

    # Query 内容校验。
    if not _validate_rewritten_query(rewrite_result, anchors):
        return False

    # Query 不能等同于用户原问题（未改写）。
    user_question = state.get("user_question", "").strip().rstrip("？?。.!！")
    rewritten = rewrite_result.get("query", "").strip().rstrip("？?。.!！")
    if rewritten == user_question:
        return False

    return True


def _finalize_rag_query(
    state: ReportChatState,
    rule_query: RagSearchRequest,
    anchors: dict,
    rewrite_result: dict | None,
    rewrite_attempted: bool,
) -> ReportChatState:
    """融合规则 query 与 LLM rewrite，写入最终 State。"""
    if rewrite_result is not None and _accept_rewrite(rewrite_result, state, anchors):
        doc_types = rewrite_result.get("doc_types", []) or ["制度", "标准", "案例"]
        rewritten_query = rewrite_result["query"]

        state["rag_query"] = _build_rag_request(
            query_text=rewritten_query,
            doc_types=doc_types,
            scene=state.get("scene", "essential_safety"),
        )
        state["rewritten_query"] = rewritten_query
        state["query_keywords"] = rewrite_result.get("query_keywords", [])
        state["query_rewrite_reason"] = rewrite_result.get("reason", "")
        state["query_rewrite_confidence"] = rewrite_result.get("confidence", 0.0)
        state["query_rewrite_source"] = "llm"
    else:
        source = "fallback" if rewrite_attempted else "rule"
        state["rag_query"] = rule_query.model_dump()
        state["rewritten_query"] = ""
        state["query_keywords"] = []
        state["query_rewrite_reason"] = ""
        state["query_rewrite_confidence"] = 0.0
        state["query_rewrite_source"] = source

    return state


# ── Main Entry ──────────────────────────────────────────

def build_rag_query_node(state: ReportChatState) -> ReportChatState:
    """基于用户问题和当前报告锚点构造 RAG 查询请求。

    Sprint6.1 升级为五层架构：
      1. 业务锚点提取 — 从 State 各字段汇总锚点信息。
      2. 规则 Query — 原有拼接逻辑，始终计算基线。
      3. LLM Rewrite — 配置开启时调用（rag_use_query_rewrite=True）。
      4. Query 校验 — 锚点完整性 + 边界词检查 + doc_type 清洗。
      5. 决策融合 — LLM 通过校验则用改写 query，否则 fallback 到规则。

    Args:
        state: 当前 State，应包含 need_rag=True 及相关报告字段。

    Returns:
        更新了 rag_query 及相关字段的 State。
    """
    errors: list[dict] = state.get("errors", [])

    # Layer 1: 业务锚点提取。
    anchors = _extract_business_anchors(state)

    # Layer 2: 规则 Query（基线，始终计算）。
    rule_query = _build_rule_query(state, anchors)

    # Layer 3: LLM Rewrite（仅配置开启时）。
    rewrite_result = None
    rewrite_attempted = False
    if settings.rag_use_query_rewrite and state.get("need_rag", False):
        rewrite_attempted = True
        rewrite_result = _llm_rewrite_query(state, anchors)

    # Layer 4+5: 校验 + 决策融合。
    state = _finalize_rag_query(state, rule_query, anchors, rewrite_result, rewrite_attempted)

    state["errors"] = errors
    return state
