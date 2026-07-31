import json
import re
from typing import Any

from app.modules.evaluation_center.domain.enums import EvaluatorKey, EvaluatorType

EvaluatorResult = dict[str, Any]
# {"evaluator_key": str, "evaluator_type": str, "score": float, "passed": bool, "reason": str, "violations": list}


def _clean_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
    return cleaned


def _try_parse_json(text: str) -> dict | list | None:
    try:
        return json.loads(_clean_json(text))
    except (json.JSONDecodeError, TypeError):
        return None


def check_json_format(output: str) -> EvaluatorResult:
    parsed = _try_parse_json(output)
    if parsed is not None:
        return {
            "evaluator_key": EvaluatorKey.JSON_FORMAT.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 1.0,
            "passed": True,
            "reason": "输出是合法 JSON",
            "violations": [],
        }
    cleaned = _clean_json(output)
    if not cleaned:
        return {
            "evaluator_key": EvaluatorKey.JSON_FORMAT.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "模型输出为空",
            "violations": ["输出为空"],
        }
    try:
        json.loads(cleaned)
        return {
            "evaluator_key": EvaluatorKey.JSON_FORMAT.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 1.0,
            "passed": True,
            "reason": "输出是合法 JSON",
            "violations": [],
        }
    except json.JSONDecodeError as e:
        return {
            "evaluator_key": EvaluatorKey.JSON_FORMAT.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": f"JSON 解析失败: {e.msg}",
            "violations": [f"JSON 解析错误: {e.msg}"],
        }


def check_schema_compliance(output: str, schema: dict | None) -> EvaluatorResult:
    if not schema:
        return {
            "evaluator_key": EvaluatorKey.SCHEMA_COMPLIANCE.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 1.0,
            "passed": True,
            "reason": "未定义 Schema，跳过校验",
            "violations": [],
        }
    parsed = _try_parse_json(output)
    if parsed is None:
        return {
            "evaluator_key": EvaluatorKey.SCHEMA_COMPLIANCE.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出不是合法 JSON，无法校验 Schema",
            "violations": ["非 JSON 输出"],
        }
    if not isinstance(parsed, dict):
        return {
            "evaluator_key": EvaluatorKey.SCHEMA_COMPLIANCE.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出不是 JSON 对象",
            "violations": ["期望 JSON 对象，实际为数组或标量"],
        }

    violations: list[str] = []
    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required_fields:
        if field not in parsed:
            violations.append(f"缺少必填字段: {field}")

    if violations:
        return {
            "evaluator_key": EvaluatorKey.SCHEMA_COMPLIANCE.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "Schema 校验未通过",
            "violations": violations,
        }

    return {
        "evaluator_key": EvaluatorKey.SCHEMA_COMPLIANCE.value,
        "evaluator_type": EvaluatorType.DETERMINISTIC.value,
        "score": 1.0,
        "passed": True,
        "reason": "Schema 校验通过",
        "violations": [],
    }


def check_field_completeness(output: str, required_fields: list[str] | None) -> EvaluatorResult:
    if not required_fields:
        required_fields = ["title", "priority"]
    parsed = _try_parse_json(output)
    if parsed is None:
        return {
            "evaluator_key": EvaluatorKey.FIELD_COMPLETENESS.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出不是合法 JSON",
            "violations": ["非 JSON 输出"],
        }
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = [parsed]
    else:
        return {
            "evaluator_key": EvaluatorKey.FIELD_COMPLETENESS.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出格式不支持字段完整性检查",
            "violations": [],
        }

    violations: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for field in required_fields:
            if field not in item or item[field] is None or (isinstance(item[field], str) and not item[field].strip()):
                violations.append(f"第 {i + 1} 项缺少或为空字段: {field}")

    passed = len(violations) == 0
    return {
        "evaluator_key": EvaluatorKey.FIELD_COMPLETENESS.value,
        "evaluator_type": EvaluatorType.DETERMINISTIC.value,
        "score": 1.0 if passed else max(0.0, 1.0 - len(violations) * 0.2),
        "passed": passed,
        "reason": "字段完整性检查通过" if passed else f"发现 {len(violations)} 个字段问题",
        "violations": violations,
    }


def check_enum_values(output: str, field_enum_map: dict[str, set] | None) -> EvaluatorResult:
    if not field_enum_map:
        field_enum_map = {"priority": {"P0", "P1", "P2", "P3", "critical", "high", "medium", "low"}}
    parsed = _try_parse_json(output)
    if parsed is None:
        return {
            "evaluator_key": EvaluatorKey.ENUM_CHECK.value,
            "evaluator_type": EvaluatorType.DETERMINISTIC.value,
            "score": 0.0,
            "passed": False,
            "reason": "输出不是合法 JSON",
            "violations": ["非 JSON 输出"],
        }
    items = [parsed] if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

    violations: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for field, valid_values in field_enum_map.items():
            if field in item:
                val = str(item[field])
                if val not in valid_values:
                    violations.append(f"第 {i + 1} 项字段 '{field}' 值 '{val}' 不在允许范围内: {valid_values}")

    passed = len(violations) == 0
    return {
        "evaluator_key": EvaluatorKey.ENUM_CHECK.value,
        "evaluator_type": EvaluatorType.DETERMINISTIC.value,
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "reason": "枚举值检查通过" if passed else f"发现 {len(violations)} 个非法枚举值",
        "violations": violations,
    }


def check_response_length(output: str, min_length: int = 10, max_length: int = 10000) -> EvaluatorResult:
    length = len(output.strip())
    passed = min_length <= length <= max_length
    violations: list[str] = []
    if length < min_length:
        violations.append(f"输出过短: {length} 字符 (最小 {min_length})")
    if length > max_length:
        violations.append(f"输出过长: {length} 字符 (最大 {max_length})")
    return {
        "evaluator_key": EvaluatorKey.RESPONSE_LENGTH.value,
        "evaluator_type": EvaluatorType.DETERMINISTIC.value,
        "score": 1.0 if passed else (0.3 if length < min_length else 0.5),
        "passed": passed,
        "reason": "响应长度合理" if passed else f"响应长度 {length} 超出范围 [{min_length}, {max_length}]",
        "violations": violations,
    }


CODE_EVALUATOR_REGISTRY: dict[str, callable] = {
    EvaluatorKey.JSON_FORMAT.value: check_json_format,
    EvaluatorKey.SCHEMA_COMPLIANCE.value: check_schema_compliance,
    EvaluatorKey.FIELD_COMPLETENESS.value: check_field_completeness,
    EvaluatorKey.ENUM_CHECK.value: check_enum_values,
    EvaluatorKey.RESPONSE_LENGTH.value: check_response_length,
}


def run_all_code_evaluators(
    output: str,
    schema: dict | None = None,
    required_fields: list[str] | None = None,
    field_enum_map: dict[str, set] | None = None,
) -> list[EvaluatorResult]:
    results: list[EvaluatorResult] = []
    for key, evaluator_fn in CODE_EVALUATOR_REGISTRY.items():
        try:
            if key == "schema_compliance":
                result = evaluator_fn(output, schema)
            elif key == "field_completeness":
                result = evaluator_fn(output, required_fields)
            elif key == "enum_check":
                result = evaluator_fn(output, field_enum_map)
            else:
                result = evaluator_fn(output)
            results.append(result)
        except Exception as e:
            results.append({
                "evaluator_key": key,
                "evaluator_type": "deterministic",
                "score": 0.0,
                "passed": False,
                "reason": f"评估器执行异常: {e}",
                "violations": [str(e)],
            })
    return results
