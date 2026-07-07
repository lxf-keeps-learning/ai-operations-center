"""
AnalyzeReasonNode — 调用 LLM 分析异常原因。

职责：
1. 从 operation_analysis.md 读取分析 Prompt。
2. 从 system_prompt.md 读取系统级角色定义。
3. 将 metrics、abnormal_items、evidence 注入 Prompt 模板。
4. 调用 DeepSeek LLM 进行原因分析。
5. LLM 调用失败时不崩溃，写入 errors 并提供兜底文本。

该节点只在存在异常项时调用 LLM。如果无异常，直接返回"未发现异常"。
"""
import json
from pathlib import Path

from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client

# Prompt 文件目录
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """从 prompts 目录加载 Prompt 模板文件。"""
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def analyze_reason_node(state: OperationState) -> OperationState:
    """
    分析异常原因。

    无异常时直接返回，不浪费 LLM 调用。
    有异常时加载 Prompt 模板，注入数据后调用 DeepSeek。
    """
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    page_ctx = state.get("page_context", {})
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    # 无异常 → 跳过 LLM 分析
    if not abnormal:
        state["reason_analysis"] = "当前时段未发现明显异常，所有指标均在正常范围内。"
        return state

    # 加载 Prompt 模板
    template = _load_prompt("operation_analysis.md")
    if not template:
        template = "分析以下异常: {abnormal_items}"

    system = _load_prompt("system_prompt.md")

    # 将 State 数据注入 Prompt 占位符
    prompt = template.format(
        page_context=json.dumps(page_ctx, ensure_ascii=False, indent=2),
        metrics=json.dumps(metrics, ensure_ascii=False, indent=2),
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
    )

    # 调用 DeepSeek LLM（system 作为 system_prompt，分析模板作为 user_message）
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
