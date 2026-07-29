import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.entities import PromptRenderResult
from app.modules.prompt_center.domain.enums import Environment
from app.modules.prompt_center.domain.exceptions import (
    prompt_not_found,
    variable_missing,
    version_not_found,
)
from app.modules.prompt_center.infrastructure.models import PromptVersion
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_def_repo,
    prompt_release_repo,
    prompt_variable_repo,
    prompt_version_repo,
)

logger = logging.getLogger(__name__)

_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render_prompt(
    db: Session,
    prompt_key: str,
    environment: str = Environment.DEVELOPMENT.value,
    version: str | None = None,
    variables: dict[str, Any] | None = None,
    user_question: str | None = None,
) -> PromptRenderResult:
    prompt = prompt_def_repo.get_by_key(db, prompt_key)
    if prompt is None:
        raise prompt_not_found(prompt_key)

    prompt_vars = prompt_variable_repo.get_by_prompt(db, prompt.id)
    var_values = variables or {}

    if prompt.deleted:
        raise prompt_not_found(prompt_key)

    if environment == Environment.PRODUCTION.value:
        if version:
            version_record = _get_version_by_str(db, prompt.id, version)
        else:
            release = prompt_release_repo.get_active(db, prompt.id, Environment.PRODUCTION.value)
            if release is None:
                raise prompt_not_found(f"{prompt_key}: 生产环境未发布版本")
            version_record = prompt_version_repo.get_by_id(db, release.version_id)
        if version_record is None:
            raise version_not_found(0)
    else:
        if version:
            version_record = _get_version_by_str(db, prompt.id, version)
        else:
            version_record = prompt_version_repo.get_published(db, prompt.id, environment)

    if version_record is None:
        version_records = prompt_version_repo.get_by_prompt(db, prompt.id)
        if version_records:
            version_record = version_records[0]
        else:
            from app.modules.prompt_center.domain.exceptions import PROMPT_NOT_FOUND
            raise PROMPT_NOT_FOUND

    _check_required_variables(prompt_vars, var_values)
    _check_template_variables(version_record, var_values)

    system_content = version_record.system_content or ""
    business_parts = _build_business_content(version_record)
    runtime_context = _build_runtime_context(prompt_vars, var_values)
    messages = _build_messages(
        system_content=system_content,
        business_content=business_parts,
        runtime_context=runtime_context,
        user_question=user_question or var_values.get("user_question", ""),
    )

    return PromptRenderResult(
        prompt_id=prompt.id,
        prompt_key=prompt.prompt_key,
        prompt_name=prompt.prompt_name,
        version=version_record.version,
        environment=environment,
        messages=messages,
        variables=var_values,
        model_config_data=version_record.model_config or {},
        output_schema=version_record.output_schema,
        langsmith_commit_hash=version_record.langsmith_commit_hash,
        langsmith_tag=version_record.langsmith_tag,
    )


def preview_prompt(
    db: Session,
    prompt_id: int,
    version_id: int,
    variables: dict[str, Any] | None = None,
    user_question: str | None = None,
) -> PromptRenderResult:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)

    version_record = prompt_version_repo.get_by_id(db, version_id)
    if version_record is None or version_record.prompt_id != prompt_id:
        raise version_not_found(version_id)

    prompt_vars = prompt_variable_repo.get_by_prompt(db, prompt_id)
    var_values = _build_preview_variables(prompt_vars, variables)

    _check_template_variables(version_record, var_values)

    system_content = version_record.system_content or ""
    business_parts = _build_business_content(version_record)
    runtime_context = _build_runtime_context(prompt_vars, var_values)
    messages = _build_messages(
        system_content=system_content,
        business_content=business_parts,
        runtime_context=runtime_context,
        user_question=user_question or var_values.get("user_question", ""),
    )

    return PromptRenderResult(
        prompt_id=prompt.id,
        prompt_key=prompt.prompt_key,
        prompt_name=prompt.prompt_name,
        version=version_record.version,
        environment="preview",
        messages=messages,
        variables=var_values,
        model_config_data=version_record.model_config or {},
        output_schema=version_record.output_schema,
        langsmith_commit_hash=version_record.langsmith_commit_hash,
        langsmith_tag=version_record.langsmith_tag,
    )


def render_to_messages(
    db: Session,
    prompt_key: str,
    environment: str = Environment.DEVELOPMENT.value,
    variables: dict[str, Any] | None = None,
    user_question: str | None = None,
) -> list[dict]:
    result = render_prompt(
        db=db,
        prompt_key=prompt_key,
        environment=environment,
        variables=variables,
        user_question=user_question,
    )
    return result.messages


def _get_version_by_str(db: Session, prompt_id: int, version_str: str) -> PromptVersion | None:
    records = prompt_version_repo.get_by_prompt(db, prompt_id)
    for r in records:
        if r.version == version_str:
            return r
    return None


def _check_required_variables(prompt_vars: list, var_values: dict[str, Any]) -> None:
    for v in prompt_vars:
        if v.required and v.variable_key not in var_values:
            if v.variable_key != "user_question":
                raise variable_missing(v.variable_key)


def _build_preview_variables(
    prompt_vars: list,
    provided: dict[str, Any] | None,
) -> dict[str, Any]:
    """预览允许缺少运行时变量，并用默认值、示例值或醒目标记补齐。"""
    values = dict(provided or {})
    for variable in prompt_vars:
        if variable.variable_key in values:
            continue
        raw_value = variable.example_value or variable.default_value
        if raw_value is not None:
            if variable.data_type in {"object", "array"}:
                try:
                    values[variable.variable_key] = json.loads(raw_value)
                except (TypeError, json.JSONDecodeError):
                    values[variable.variable_key] = raw_value
            else:
                values[variable.variable_key] = raw_value
        elif variable.required and variable.variable_key != "user_question":
            values[variable.variable_key] = f"<未提供：{variable.variable_name}>"
    return values


def _check_template_variables(version_record: PromptVersion, var_values: dict[str, Any]) -> None:
    content_fields = [
        version_record.system_content or "",
        version_record.business_role_content or "",
        version_record.business_goal_content or "",
        version_record.output_requirement or "",
    ]
    for field in content_fields:
        for match in _TEMPLATE_VAR_PATTERN.findall(field):
            if match not in var_values and match != "business_rules" and match != "positive_examples" and match != "negative_examples":
                logger.warning("模板变量 %s 未提供值", match)


def _build_business_content(version: PromptVersion) -> str:
    parts: list[str] = []
    if version.business_role_content:
        parts.append(version.business_role_content)
    if version.business_goal_content:
        parts.append(version.business_goal_content)
    if version.business_rules:
        rules = version.business_rules
        if isinstance(rules, list):
            parts.append("## 业务规则")
            for i, rule in enumerate(rules, 1):
                if isinstance(rule, dict):
                    if rule.get("enabled", True):
                        parts.append(f"{i}. {rule.get('content', '')}")
                else:
                    parts.append(f"{i}. {rule}")
    if version.output_requirement:
        parts.append(version.output_requirement)
    if version.positive_examples:
        parts.append("## 正例")
        for ex in version.positive_examples:
            if isinstance(ex, dict):
                parts.append(f"- {ex.get('content', '')}")
            else:
                parts.append(f"- {ex}")
    if version.negative_examples:
        parts.append("## 反例")
        for ex in version.negative_examples:
            if isinstance(ex, dict):
                parts.append(f"- {ex.get('content', '')}")
            else:
                parts.append(f"- {ex}")
    return "\n\n".join(parts)


def _build_runtime_context(prompt_vars: list, var_values: dict[str, Any]) -> str:
    parts: list[str] = []
    for v in prompt_vars:
        key = v.variable_key
        if key in var_values and key != "user_question":
            val = var_values[key]
            if val is not None:
                if isinstance(val, (dict, list)):
                    val_str = json.dumps(val, ensure_ascii=False, indent=2)
                else:
                    val_str = str(val)
                parts.append(f"{v.variable_name}：\n{val_str}")
    return "\n\n".join(parts)


def _build_messages(
    system_content: str,
    business_content: str,
    runtime_context: str,
    user_question: str,
) -> list[dict]:
    messages: list[dict] = []

    system_parts: list[str] = []
    if system_content:
        system_parts.append(system_content)
    full_system = "\n\n".join(system_parts)
    if full_system:
        messages.append({"role": "system", "content": full_system})

    user_parts: list[str] = []
    if business_content:
        user_parts.append(business_content)
    if runtime_context:
        user_parts.append(f"## 当前上下文\n\n{runtime_context}")
    if user_question:
        user_parts.append(f"## 用户问题\n\n{user_question}")

    if user_parts:
        messages.append({"role": "user", "content": "\n\n".join(user_parts)})

    return messages
