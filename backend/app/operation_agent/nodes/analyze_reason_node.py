"""AnalyzeReasonNode - analyze abnormal reasons with fast LLM fallback."""

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


def analyze_reason_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    page_ctx = state.get("page_context", {})
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    if not abnormal:
        state["reason_analysis"] = "当前时段未发现明显异常，所有指标均在正常范围内。"
        return state

    template = _load_prompt("operation_analysis.md") or "分析以下异常: {abnormal_items}"
    system = _load_prompt("system_prompt.md")

    prompt = template.format(
        page_context=json.dumps(page_ctx, ensure_ascii=False, indent=2),
        metrics=json.dumps(metrics, ensure_ascii=False, indent=2),
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
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
            "action_type": "analyze_reason",
            "model_name": result.model,
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "success": 1 if result.success else 0,
            "error_message": result.error_message if not result.success else None,
        })
        if result.success and result.content.strip():
            state["reason_analysis"] = result.content
        else:
            errors.append(
                {"node": "analyze_reason", "message": f"LLM 调用失败: {result.error_message}"}
            )
            state["reason_analysis"] = _fallback_reason(
                abnormal,
                metrics,
                evidence,
                result.error_message,
            )
    except Exception as e:
        llm_usages.append({
            "action_type": "analyze_reason",
            "model_name": "deepseek-chat",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": 0,
            "error_message": str(e),
        })
        errors.append({"node": "analyze_reason", "message": f"LLM 调用异常: {e}"})
        state["reason_analysis"] = _fallback_reason(abnormal, metrics, evidence, str(e))

    state["llm_usages"] = llm_usages
    state["errors"] = errors
    return state


def _fallback_reason(
    abnormal_items: list[dict],
    metrics: list[dict],
    evidence: list[dict],
    failure_reason: str | None = None,
) -> str:
    high_items = [
        item
        for item in abnormal_items
        if item.get("severity") in {"critical", "high"}
    ]
    warning_items = [
        item
        for item in abnormal_items
        if item.get("severity") in {"warning", "medium"}
    ]
    metric_names = [
        item.get("metric_name", "")
        for item in abnormal_items[:3]
        if item.get("metric_name")
    ]

    first_line = "DeepSeek 分析调用未返回有效结果，已基于规则和 Tool Center 数据生成兜底原因分析。"
    if failure_reason:
        first_line = (
            "DeepSeek 分析调用未返回有效结果"
            f"（{failure_reason}），已基于规则和 Tool Center 数据生成兜底原因分析。"
        )

    lines = [
        first_line,
        f"本次共读取 {len(metrics)} 个指标/派生指标、{len(evidence)} 条证据。",
    ]
    if high_items:
        lines.append(f"其中 {len(high_items)} 项为高等级风险，应优先处理。")
    if warning_items:
        lines.append(f"另有 {len(warning_items)} 项需要持续推进闭环。")
    if metric_names:
        lines.append(f"重点关注：{'、'.join(metric_names)}。")
    lines.append("建议先核验对应告警、隐患和工单记录，再安排责任人闭环。")
    return "\n".join(lines)
