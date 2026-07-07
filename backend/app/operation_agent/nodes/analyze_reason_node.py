import json
from pathlib import Path

from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def analyze_reason_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    page_ctx = state.get("page_context", {})
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    if not abnormal:
        state["reason_analysis"] = "当前时段未发现明显异常，所有指标均在正常范围内。"
        return state

    template = _load_prompt("operation_analysis.md")
    if not template:
        template = "分析以下异常: {abnormal_items}"

    system = _load_prompt("system_prompt.md")

    prompt = template.format(
        page_context=json.dumps(page_ctx, ensure_ascii=False, indent=2),
        metrics=json.dumps(metrics, ensure_ascii=False, indent=2),
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
    )

    try:
        result: LlmResult = llm_client.chat(prompt_content=system or None, user_message=prompt)
        if result.success:
            state["reason_analysis"] = result.content
        else:
            errors.append({"node": "analyze_reason", "message": f"LLM 调用失败: {result.error_message}"})
            state["reason_analysis"] = "（LLM 分析不可用，请稍后重试）"
    except Exception as e:
        errors.append({"node": "analyze_reason", "message": f"LLM 调用异常: {e}"})
        state["reason_analysis"] = "（LLM 分析不可用，请稍后重试）"

    state["errors"] = errors
    return state
