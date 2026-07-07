"""GenerateAdviceNode - generate actionable advice with fast LLM fallback."""

import json
from pathlib import Path

from app.config.settings import settings
from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client

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

    try:
        result: LlmResult = llm_client.chat(
            prompt_content=system or None,
            user_message=prompt,
            timeout_seconds=settings.operation_llm_timeout_seconds,
        )
        if result.success:
            parsed = _parse_advice(result.content)
            state["advice_items"] = parsed if parsed else _fallback_advice(abnormal)
        else:
            errors.append(
                {"node": "generate_advice", "message": f"LLM 调用失败: {result.error_message}"}
            )
            state["advice_items"] = _fallback_advice(abnormal)
    except Exception as e:
        errors.append({"node": "generate_advice", "message": f"LLM 调用异常: {e}"})
        state["advice_items"] = _fallback_advice(abnormal)

    state["errors"] = errors
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
                "owner_role": "安全运营负责人",
                "action": f"核查 {name} 对应数据和现场记录，确认原因并制定整改计划。",
                "expected_result": f"推动 {name} 完成闭环处置。",
                "evidence": item.get("evidence", []),
            }
        )
    return items
