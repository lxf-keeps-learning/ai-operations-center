"""
GenerateAdviceNode — 调用 LLM 或规则兜底生成改进建议。

职责：
1. 从 operation_advice.md 读取建议生成 Prompt。
2. 从 system_prompt.md 读取系统级角色定义。
3. 将 abnormal_items、reason_analysis 注入 Prompt 模板。
4. 调用 DeepSeek LLM 生成结构化建议。
5. LLM 返回解析失败时使用规则兜底（_fallback_advice）。

建议结构：
  { title, priority(P0/P1/P2), owner_role, action, expected_result }

建议输出规则：
- 无异常时不生成建议。
- priority 只允许 P0 / P1 / P2。
- action 必须可执行、具体。
- 禁止"加强管理、持续关注、提高意识"等空泛表达。
"""
import json
from pathlib import Path

from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult, llm_client

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """从 prompts 目录加载 Prompt 模板文件。"""
    path = _PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate_advice_node(state: OperationState) -> OperationState:
    """
    生成改进建议。

    优先调用 LLM，LLM 返回结构化 JSON 列表。
    如果 LLM 返回格式异常，使用规则兜底生成基础建议。
    """
    reason = state.get("reason_analysis", "")
    abnormal = state.get("abnormal_items", [])
    evidence = state.get("evidence", [])
    errors: list[dict] = state.get("errors", [])

    # 无异常 → 无需建议
    if not abnormal:
        state["advice_items"] = []
        return state

    # 加载 Prompt 模板
    template = _load_prompt("operation_advice.md")
    if not template:
        template = "基于异常生成建议: {abnormal_items}"

    system = _load_prompt("system_prompt.md")

    # 注入数据
    prompt = template.format(
        abnormal_items=json.dumps(abnormal, ensure_ascii=False, indent=2),
        reason_analysis=reason,
        evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
    )

    # 调用 LLM 生成建议
    try:
        result: LlmResult = llm_client.chat(prompt_content=system or None, user_message=prompt)
        if result.success:
            parsed = _parse_advice(result.content)
            state["advice_items"] = parsed if parsed else _fallback_advice(abnormal)
        else:
            errors.append({"node": "generate_advice", "message": f"LLM 调用失败: {result.error_message}"})
            state["advice_items"] = _fallback_advice(abnormal)
    except Exception as e:
        errors.append({"node": "generate_advice", "message": f"LLM 调用异常: {e}"})
        state["advice_items"] = _fallback_advice(abnormal)

    state["errors"] = errors
    return state


def _parse_advice(text: str) -> list[dict] | None:
    """
    解析 LLM 返回的结构化建议。

    LLM 可能返回 JSON 数组、代码块包裹的 JSON、Markdown 列表等。
    当前只支持 JSON 数组格式，其余返回 None 触发兜底。
    """
    cleaned = text.strip()
    # 移除可能存在的 markdown 代码块标记 ```json ... ```
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
    try:
        items = json.loads(cleaned)
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _fallback_advice(abnormal: list[dict]) -> list[dict]:
    """
    规则兜底：当 LLM 不可用或返回格式异常时，基于异常项生成基础建议。

    每条建议映射一个异常项，最多生成 3 条。
    """
    items = []
    for a in abnormal[:3]:
        items.append({
            "title": f"处理 {a.get('metric_name', '')} 异常",
            "priority": "P1" if a.get("severity") == "high" else "P2",
            "owner_role": "安全运营负责人",
            "action": f"核查 {a.get('metric_name', '')} 数据，确认异常原因并制定整改计划。",
            "expected_result": f"解决 {a.get('metric_name', '')} 异常状态。",
        })
    return items
