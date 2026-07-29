import json
import logging
from typing import Any

from app.modules.evaluation_center.domain.enums import EvaluatorKey, EvaluatorType
from app.runtime.llm.client import LlmResult, llm_client

logger = logging.getLogger(__name__)

EvaluatorResult = dict[str, Any]

_JUDGE_SYSTEM_PROMPT = """你是 AI 输出质量评估专家。你的任务是对 AI 助手的输出进行评估。

你需要基于用户输入（Input）和 AI 输出（Output）进行判断，给出评分（0-1）和原因。

严格遵循以下原则：
1. 评分 1.0 表示完全符合要求，0.0 表示完全不符合。
2. 必须给出具体的判断理由。
3. 如果发现违规项，必须在 violations 中列出。
4. 只输出 JSON 格式，不要输出其他内容。
5. 输出格式: {{"score": 0.0-1.0, "passed": true/false, "reason": "...", "violations": [...]}}
"""


def _build_judge_prompt(evaluator_key: str, input_text: str, output_text: str) -> str:
    prompts = {
        EvaluatorKey.QUESTION_ANSWERED.value: (
            "## 评估维度：是否回答问题\n\n"
            f"## Input（用户问题）\n{input_text}\n\n"
            f"## Output（AI 回答）\n{output_text}\n\n"
            "## 判断标准\n"
            "1. AI 回答是否直接回应用户问题？\n"
            "2. 是否答非所问？\n"
            "3. 是否回避问题核心？\n\n"
            "## 输出\n"
            '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": ["违规项列表"]}'
        ),
        EvaluatorKey.DATA_GROUNDED.value: (
            "## 评估维度：是否基于输入数据\n\n"
            f"## Input（输入数据）\n{input_text}\n\n"
            f"## Output（AI 回答）\n{output_text}\n\n"
            "## 判断标准\n"
            "1. AI 回答中的结论、数字、事实是否能在 Input 中找到依据？\n"
            "2. 是否存在 Input 中没有数据支撑的断言？\n"
            "3. 是否过度推断？\n\n"
            "## 输出\n"
            '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": ["无数据支撑的断言列表"]}'
        ),
        EvaluatorKey.NO_HALLUCINATION.value: (
            "## 评估维度：是否虚构数据\n\n"
            f"## Input（输入数据）\n{input_text}\n\n"
            f"## Output（AI 回答）\n{output_text}\n\n"
            "## 判断标准\n"
            "1. Output 中是否有 Input 不存在的具体数据（数字、日期、事件、引用等）？\n"
            "2. 是否虚构了制度名称、标准编号、历史案例？\n"
            "3. 不确定性表述（可能、也许、建议核查）不算虚构。\n\n"
            "## 输出\n"
            '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": ["虚构内容列表"]}'
        ),
        EvaluatorKey.EVIDENCE_PROVIDED.value: (
            "## 评估维度：是否提供依据\n\n"
            f"## Input（输入数据）\n{input_text}\n\n"
            f"## Output（AI 回答）\n{output_text}\n\n"
            "## 判断标准\n"
            "1. 关键结论是否附带了数据引用或来源说明？\n"
            "2. 是否给出了判断依据？\n"
            "3. 如果数据不足，是否明确说明？\n\n"
            "## 输出\n"
            '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": ["缺乏依据的结论列表"]}'
        ),
        EvaluatorKey.ACTIONABLE_ADVICE.value: (
            "## 评估维度：是否给出可执行建议\n\n"
            f"## Input（输入数据）\n{input_text}\n\n"
            f"## Output（AI 回答）\n{output_text}\n\n"
            "## 判断标准\n"
            "1. 建议是否具体可执行？\n"
            "2. 是否包含空泛表述（加强管理、持续关注、提高意识）？\n"
            "3. 是否包含具体行动步骤？\n\n"
            "## 输出\n"
            '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": ["空泛建议列表"]}'
        ),
    }
    return prompts.get(evaluator_key, (
        f"## 评估维度：{evaluator_key}\n\n"
        f"## Input（输入）\n{input_text}\n\n"
        f"## Output（输出）\n{output_text}\n\n"
        "## 输出\n"
        '{"score": 0-1, "passed": true/false, "reason": "判断理由", "violations": []}'
    ))


def _parse_judge_result(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return {"score": 0.0, "passed": False, "reason": "Judge 输出解析失败", "violations": [text[:200]]}


def run_llm_judge(
    evaluator_key: str,
    input_text: str,
    output_text: str,
) -> EvaluatorResult:
    if not output_text or not output_text.strip():
        return {
            "evaluator_key": evaluator_key,
            "evaluator_type": EvaluatorType.LLM_JUDGE.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出为空，无法评估",
            "violations": ["输出为空"],
        }

    judge_prompt = _build_judge_prompt(evaluator_key, input_text, output_text)

    try:
        result: LlmResult = llm_client.chat(
            prompt_content=_JUDGE_SYSTEM_PROMPT,
            user_message=judge_prompt,
        )
        if result.success:
            parsed = _parse_judge_result(result.content)
            return {
                "evaluator_key": evaluator_key,
                "evaluator_type": EvaluatorType.LLM_JUDGE.value,
                "score": parsed.get("score", 0.0),
                "passed": parsed.get("passed", False),
                "reason": parsed.get("reason", ""),
                "violations": parsed.get("violations", []),
            }
        return {
            "evaluator_key": evaluator_key,
            "evaluator_type": EvaluatorType.LLM_JUDGE.value,
            "score": 0.0,
            "passed": False,
            "reason": f"LLM Judge 调用失败: {result.error_message}",
            "violations": [],
        }
    except Exception as e:
        logger.exception("LLM Judge 执行异常: %s", evaluator_key)
        return {
            "evaluator_key": evaluator_key,
            "evaluator_type": EvaluatorType.LLM_JUDGE.value,
            "score": 0.0,
            "passed": False,
            "reason": f"LLM Judge 异常: {e}",
            "violations": [str(e)],
        }


def run_all_llm_judges(input_text: str, output_text: str) -> list[EvaluatorResult]:
    keys = [
        EvaluatorKey.QUESTION_ANSWERED.value,
        EvaluatorKey.DATA_GROUNDED.value,
        EvaluatorKey.NO_HALLUCINATION.value,
        EvaluatorKey.EVIDENCE_PROVIDED.value,
        EvaluatorKey.ACTIONABLE_ADVICE.value,
    ]
    results: list[EvaluatorResult] = []
    for key in keys:
        try:
            result = run_llm_judge(key, input_text, output_text)
            results.append(result)
        except Exception as e:
            logger.exception("LLM Judge %s 异常", key)
            results.append({
                "evaluator_key": key,
                "evaluator_type": EvaluatorType.LLM_JUDGE.value,
                "score": 0.0,
                "passed": False,
                "reason": f"异常: {e}",
                "violations": [str(e)],
            })
    return results
