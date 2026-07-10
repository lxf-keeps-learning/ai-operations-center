"""基于报告上下文、evidence 和 RAG 检索结果生成回答。

职责边界（Sprint6）：
  当 used_rag=True 时，使用 RAG 增强 Prompt（rag_answer.md）；
  当 used_rag=False 时，继续使用原有的报告 Prompt（report_answer.md）。

核心设计原则：
  1. 不破坏 Sprint5 原有报告回答能力。
  2. RAG 只作为补充依据，不覆盖报告结论。
  3. LLM 不能编造报告中不存在的数据和 RAG 中不存在的知识。
  4. 各种失败场景都有兜底回答，LLM 调用失败时不阻塞 Graph。
"""

import json
from pathlib import Path

from app.config.settings import settings
from app.report_chat_agent.state import ReportChatState
from app.report_chat_agent.stream_context import get_answer_stream_callback
from app.runtime.llm.client import LlmResult, llm_client
from app.security.content_moderator import ModerationAction, content_moderator

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate_report_answer_node(state: ReportChatState) -> ReportChatState:
    user_question = state.get("user_question", "")
    report_context = state.get("report_context", {})
    retrieved_context = state.get("retrieved_context", [])
    evidence = state.get("evidence", [])
    evidence_refs = state.get("evidence_refs", [])
    merged_context = state.get("merged_context", [])
    rag_results = state.get("rag_results", [])
    used_rag = state.get("used_rag", False)
    rag_query = state.get("rag_query", {})
    chat_history = state.get("chat_history", [])
    errors: list[dict] = state.get("errors", [])

    if _has_load_report_error(errors):
        state["final_answer"] = (
            "当前报告不存在或无法加载，因此不能进行报告追问。"
            "请先确认分析记录是否已生成成功，再从报告详情页发起追问。"
        )
        state["answer_type"] = "insufficient_evidence"
        state["evidence_refs"] = evidence_refs
        state["errors"] = errors
        return state

    if state.get("need_rag") and rag_query and not rag_results:
        state["final_answer"] = _rag_insufficient_answer(user_question, report_context, errors)
        state["answer_type"] = "insufficient_evidence"
        state["evidence_refs"] = evidence_refs
        state["errors"] = errors
        return state

    if not _has_meaningful_context(report_context, retrieved_context, evidence, rag_results, merged_context):
        state["final_answer"] = (
            "当前报告未提供足够信息，因此不能给出确定判断。"
        )
        state["answer_type"] = "insufficient_evidence"
        state["evidence_refs"] = evidence_refs
        state["errors"] = errors
        return state

    # 根据是否使用 RAG 选择 Prompt 模板。
    if used_rag and rag_results:
        template = _load_prompt("rag_answer.md")
    else:
        template = _load_prompt("report_answer.md")

    system = _load_prompt("system_prompt.md")

    prompt = template.format(
        user_question=user_question,
        report_context=json.dumps(report_context, ensure_ascii=False, indent=2),
        retrieved_context=json.dumps(retrieved_context, ensure_ascii=False, indent=2),
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
        merged_context=json.dumps(merged_context, ensure_ascii=False, indent=2),
        rag_results=json.dumps(rag_results, ensure_ascii=False, indent=2),
        chat_history=json.dumps(chat_history[-4:], ensure_ascii=False, indent=2),
    )

    llm_usages: list[dict] = state.get("llm_usages", [])

    try:
        stream_callback = get_answer_stream_callback()
        if stream_callback:
            result = llm_client.stream_chat(
                prompt_content=system,
                user_message=prompt,
                on_chunk=stream_callback,
                timeout_seconds=settings.operation_llm_timeout_seconds,
            )
        else:
            result = llm_client.chat(
                prompt_content=system,
                user_message=prompt,
                timeout_seconds=settings.operation_llm_timeout_seconds,
            )
        llm_usages.append({
            "action_type": "report_answer",
            "model_name": result.model,
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "success": 1 if result.success else 0,
            "error_message": result.error_message if not result.success else None,
        })
        if result.success and result.content.strip():
            state["final_answer"] = result.content
            state["answer_type"] = "normal"
        else:
            errors.append({
                "node": "generate_answer",
                "message": f"LLM 调用失败: {result.error_message}",
            })
            state["final_answer"] = _fallback_answer(report_context, retrieved_context, rag_results)
            state["answer_type"] = "normal"
    except Exception as e:
        llm_usages.append({
            "action_type": "report_answer",
            "model_name": "deepseek-chat",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": 0,
            "error_message": str(e),
        })
        errors.append({
            "node": "generate_answer",
            "message": f"LLM 调用异常: {e}",
        })
        state["final_answer"] = _fallback_answer(report_context, retrieved_context, rag_results)
        state["answer_type"] = "normal"

    state["llm_usages"] = llm_usages
    state["errors"] = errors
    state["evidence_refs"] = evidence_refs

    moderation = content_moderator.moderate_output(state.get("final_answer", ""))
    if moderation.action == ModerationAction.MASK and moderation.masked_text:
        state["final_answer"] = moderation.masked_text
    elif moderation.action == ModerationAction.BLOCK:
        state["final_answer"] = moderation.message or "AI 生成的回答已被安全策略过滤，请尝试重新提问。"
        state["answer_type"] = "boundary"

    return state


def _has_load_report_error(errors: list[dict]) -> bool:
    return any(error.get("node") == "load_report_context" for error in errors)


def _has_meaningful_context(
    report_context: dict,
    retrieved_context: list[dict],
    evidence: list[dict],
    rag_results: list[dict],
    merged_context: list[dict],
) -> bool:
    if report_context and report_context.get("summary"):
        return True
    if retrieved_context:
        return True
    if evidence:
        return True
    if rag_results:
        return True
    if merged_context:
        return True
    return False


def _rag_insufficient_answer(
    user_question: str,
    report_context: dict,
    errors: list[dict],
) -> str:
    title = report_context.get("title", "当前报告") if report_context else "当前报告"
    has_empty_result = any(
        error.get("node") == "call_rag" and "无结果" in str(error.get("message", ""))
        for error in errors
    )
    reason = (
        "我已经尝试检索知识库，但没有找到足够匹配的制度、标准或案例依据。"
        if has_empty_result
        else "我已经尝试检索知识库，但本次检索暂时不可用或没有返回有效依据。"
    )
    return "\n".join([
        "### 结论",
        "",
        f"这个问题与《{title}》相关，但当前报告内没有足够的直接信息可以确定回答。",
        reason,
        "",
        "### 建议",
        "",
        f"可以把问题再具体到某个风险项、异常项或制度类型后重试，例如：{user_question} 的制度依据、分级规则或处置流程。",
    ])


def _fallback_answer(
    report_context: dict,
    retrieved_context: list[dict],
    rag_results: list[dict],
) -> str:
    lines = ["### 结论", ""]
    title = report_context.get("title", "运营分析报告") if report_context else "运营分析报告"
    summary = report_context.get("summary", "") if report_context else ""
    if summary:
        lines.append(f"根据当前报告《{title}》：")
        lines.append("")
        lines.append(summary[:300])
    else:
        lines.append(f"根据当前报告《{title}》中的数据分析，")

    if retrieved_context:
        lines.append("")
        lines.append("### 报告依据")
        for i, ctx in enumerate(retrieved_context[:3], 1):
            t = ctx.get("title", "")
            c = ctx.get("content", "")[:100]
            lines.append(f"{i}. {t}：{c}")

    if rag_results:
        lines.append("")
        lines.append("### 知识库补充依据")
        for i, r in enumerate(rag_results[:3], 1):
            doc_title = r.get("document_title", "")
            content = r.get("content", "")[:100]
            lines.append(f"{i}. {doc_title}：{content}")

    return "\n".join(lines)
