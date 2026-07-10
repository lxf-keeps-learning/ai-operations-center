"""GenerateAdviceNode - generate actionable advice with fast LLM fallback."""

import json
from pathlib import Path

from app.config.settings import settings
from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client
from app.security.content_moderator import ModerationAction, content_moderator

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate_advice_node(state: OperationState) -> OperationState:
    reason = state.get("reason_analysis", "")
    abnormal = state.get("abnormal_items", [])
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    if not abnormal:
        state["advice_items"] = []
        return state

    template = _load_prompt("operation_advice.md") or "基于异常生成建议: {abnormal_items}"
    system = _load_prompt("system_prompt.md")

    prompt = template.format(
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
        reason_analysis=reason,
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
    )

    llm_usages: list[dict] = state.get("llm_usages", [])

    try:
        result: LlmResult = llm_client.chat(
            prompt_content=system or None,
            user_message=prompt,
            timeout_seconds=settings.operation_llm_timeout_seconds,
        )
        llm_usages.append({
            "action_type": "generate_advice",
            "model_name": result.model,
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "success": 1 if result.success else 0,
            "error_message": result.error_message if not result.success else None,
        })
        if result.success:
            parsed = _parse_advice(result.content)
            state["advice_items"] = parsed if parsed else _fallback_advice(abnormal)
        else:
            errors.append(
                {"node": "generate_advice", "message": f"LLM 调用失败: {result.error_message}"}
            )
            state["advice_items"] = _fallback_advice(abnormal)
    except Exception as e:
        llm_usages.append({
            "action_type": "generate_advice",
            "model_name": "deepseek-chat",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": 0,
            "error_message": str(e),
        })
        errors.append({"node": "generate_advice", "message": f"LLM 调用异常: {e}"})
        state["advice_items"] = _fallback_advice(abnormal)

    state["llm_usages"] = llm_usages
    state["errors"] = errors

    advice_text = json.dumps(state.get("advice_items", []), ensure_ascii=False)
    moderation = content_moderator.moderate_output(advice_text)
    if moderation.action in (ModerationAction.MASK, ModerationAction.BLOCK):
        state["advice_items"] = []

    return state


def _parse_advice(text: str) -> list[dict] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
    try:
        items = json.loads(cleaned)
        if isinstance(items, list) and all(isinstance(item, dict) for item in items):
            return items
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _fallback_advice(abnormal: list[dict]) -> list[dict]:
    items = []
    for item in abnormal[:3]:
        name = item.get("metric_name") or item.get("message", "运营异常")
        items.append(
            {
                "title": f"处理 {name} 异常",
                "priority": "P1" if item.get("severity") in {"critical", "high"} else "P2",
                "owner_role": _owner_for_domain(item.get("domain", "safety")),
                "action": f"核查 {name} 对应数据和现场记录，确认原因并制定整改计划。",
                "expected_result": f"推动 {name} 完成闭环处置。",
                "evidence": item.get("evidence", []),
            }
        )
    return items


def _owner_for_domain(domain: str) -> str:
    return {
        "safety": "安全运营负责人",
        "maintenance": "设备运维负责人",
        "business": "经营改善负责人",
        "capability": "能力提升负责人",
    }.get(domain, "运营负责人")
