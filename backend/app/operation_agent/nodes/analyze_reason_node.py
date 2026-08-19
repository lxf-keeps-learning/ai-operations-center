"""
原因分析节点 — AnalyzeReasonNode。

职责：
  1. 将异常项、指标、证据组装 Prompt 调用 LLM 分析可能原因。
  2. LLM 调用失败时降级到基于规则的兜底分析（_fallback_reason）。
  3. 记录 LLM 调用统计（token 用量、成功/失败）。
  4. 对输出内容做安全审核（content_moderator）。
"""

import json
from pathlib import Path

from app.config.settings import settings
from app.modules.prompt_center.application.langgraph_integration import get_rendered_prompt
from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client
from app.security.content_moderator import ModerationAction, content_moderator

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def analyze_reason_node(
    state: OperationState,
    *,
    prompt_name: str = "operation_analysis.md",
    action_type: str = "analyze_reason",
) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    page_ctx = state.get("page_context", {})
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    if not abnormal:
        state["reason_analysis"] = "当前时段未发现明显异常，所有指标均在正常范围内。"
        return state

    template = _load_prompt(prompt_name) or "分析以下异常: {abnormal_items}"
    fallback_system = _load_prompt("system_prompt.md")
    fallback_user = template.format(
        page_context=json.dumps(page_ctx, ensure_ascii=False, indent=2),
        metrics=json.dumps(metrics, ensure_ascii=False, indent=2),
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
    )
    rendered_prompt = get_rendered_prompt(
        prompt_key="ioc.safety.analysis",
        environment="production",
        variables={
            "device_name": page_ctx.get("active_tab") or page_ctx.get("domain") or "IOC 运营对象",
            "realtime_data": {
                "metrics": metrics,
                "abnormal_items": abnormal,
                "evidence": evidence,
            },
            "history_data": state.get("raw_data", {}),
            "alarm_data": state.get("raw_data", {}).get("alarm", []),
        },
        user_question="请分析当前异常指标的可能原因，并说明数据依据与待核查事项。",
        fallback_messages=[
            {"role": "system", "content": fallback_system},
            {"role": "user", "content": fallback_user},
        ],
    )
    system = _message_content(rendered_prompt.messages, "system")
    prompt = _message_content(rendered_prompt.messages, "user")

    prompt_facts: dict[str, dict] = state.setdefault("prompt_facts", {})
    prompt_facts["analyze_reason"] = {
        "prompt_key": rendered_prompt.prompt_key,
        "prompt_version": rendered_prompt.version,
        "prompt_commit_hash": rendered_prompt.langsmith_commit_hash,
        "prompt_environment": rendered_prompt.environment,
    }

    llm_usages: list[dict] = state.get("llm_usages", [])

    try:
        result: LlmResult = await llm_client.achat(
            prompt_content=system or None,
            user_message=prompt,
            timeout_seconds=settings.operation_llm_timeout_seconds,
        )
        llm_usages.append({
            "action_type": action_type,
            "model_name": result.model,
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "success": 1 if result.success else 0,
            "error_message": result.error_message if not result.success else None,
            "prompt_key": rendered_prompt.prompt_key,
            "prompt_version": rendered_prompt.version,
            "prompt_commit_hash": rendered_prompt.langsmith_commit_hash,
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
            "action_type": action_type,
            "model_name": "deepseek-chat",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": 0,
            "error_message": str(e),
            "prompt_key": rendered_prompt.prompt_key,
            "prompt_version": rendered_prompt.version,
            "prompt_commit_hash": rendered_prompt.langsmith_commit_hash,
        })
        errors.append({"node": "analyze_reason", "message": f"LLM 调用异常: {e}"})
        state["reason_analysis"] = _fallback_reason(abnormal, metrics, evidence, str(e))

    state["llm_usages"] = llm_usages
    state["errors"] = errors

    moderation = content_moderator.moderate_output(state.get("reason_analysis", ""))
    if moderation.action == ModerationAction.MASK and moderation.masked_text:
        state["reason_analysis"] = moderation.masked_text
    elif moderation.action == ModerationAction.BLOCK:
        state["reason_analysis"] = "原因分析内容已被安全策略过滤。"

    return state


def _message_content(messages: list[dict], role: str) -> str:
    for message in messages:
        if message.get("role") == role:
            return str(message.get("content") or "")
    return ""


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
