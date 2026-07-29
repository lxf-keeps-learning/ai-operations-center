import json
import logging
import re
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.enums import AuditAction
from app.modules.prompt_center.domain.exceptions import (
    prompt_not_found,
    version_not_found,
)
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode

TEST_CASE_NOT_FOUND_EC = ErrorCode(code=404013, message="测试用例不存在", http_status=404, description="指定的测试用例不存在")
RELEASE_NOT_FOUND_EC = ErrorCode(code=404014, message="发布记录不存在", http_status=404, description="发布记录未找到")
from app.modules.prompt_center.infrastructure.models import PromptVersion
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_audit_log_repo,
    prompt_def_repo,
    prompt_test_case_repo,
    prompt_test_run_repo,
    prompt_version_repo,
)
from app.modules.prompt_center.schemas.test_schema import (
    DatasetTestRequest,
    EvaluationResponse,
    EvaluationSummary,
    TestCaseCreate,
    TestCaseResponse,
    TestRunRequest,
    TestRunResponse,
)
from app.runtime.llm.client import LlmResult, llm_client

logger = logging.getLogger(__name__)


def create_test_case(db: Session, prompt_id: int, data: TestCaseCreate) -> TestCaseResponse:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)
    record = prompt_test_case_repo.create(db, {
        "prompt_id": prompt_id,
        "case_name": data.case_name,
        "case_type": data.case_type,
        "input_data": data.input_data,
        "expected_output": data.expected_output,
        "source_trace_id": data.source_trace_id,
        "created_by": data.case_name,
    })
    return TestCaseResponse.model_validate(record)


def list_test_cases(db: Session, prompt_id: int) -> list[TestCaseResponse]:
    records = prompt_test_case_repo.list_by_prompt(db, prompt_id)
    return [TestCaseResponse.model_validate(r) for r in records]


def run_single_test(
    db: Session, prompt_id: int, version_id: int, data: TestRunRequest, operator_id: str | None = None,
) -> TestRunResponse:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)
    version = prompt_version_repo.get_by_id(db, version_id)
    if version is None or version.prompt_id != prompt_id:
        raise version_not_found(version_id)

    rendered_prompt = _build_test_prompt(version, data.input_data)
    run_data = {
        "prompt_id": prompt_id,
        "version_id": version_id,
        "test_case_id": data.test_case_id,
        "model_name": data.model_name or "deepseek-chat",
        "input_data": data.input_data,
        "rendered_prompt": _messages_to_text(rendered_prompt),
        "status": "running",
        "created_by": operator_id,
    }

    run_record = prompt_test_run_repo.create(db, run_data)

    try:
        system_content = _get_system_text(rendered_prompt)
        user_message = _get_user_text(rendered_prompt)

        start = perf_counter()
        result: LlmResult = llm_client.chat(
            prompt_content=system_content or None,
            user_message=user_message,
            provider_name=data.provider_name,
        )
        latency = max(1, int((perf_counter() - start) * 1000))

        structured_output = None
        if result.content:
            structured_output = _try_parse_json(result.content)

        prompt_test_run_repo.update(db, run_record.id, {
            "raw_output": result.content,
            "structured_output": structured_output,
            "token_usage": {
                "input_tokens": result.prompt_tokens,
                "output_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
            },
            "latency": latency,
            "status": "completed" if result.success else "failed",
        })
    except Exception as e:
        logger.exception("测试执行失败")
        prompt_test_run_repo.update(db, run_record.id, {
            "status": "failed",
            "raw_output": f"测试执行异常: {e}",
        })

    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": version_id,
        "action": AuditAction.TEST.value,
        "operator_id": operator_id,
    })

    return get_test_run(db, run_record.id)


def run_dataset_test(
    db: Session, prompt_id: int, version_id: int, data: DatasetTestRequest, operator_id: str | None = None,
) -> list[TestRunResponse]:
    results: list[TestRunResponse] = []
    for case_id in data.test_case_ids:
        case = prompt_test_case_repo.get_by_id(db, case_id)
        if case is None:
            continue
        run_req = TestRunRequest(
            input_data=case.input_data,
            test_case_id=case_id,
            model_name=data.model_name,
        )
        result = run_single_test(db, prompt_id, version_id, run_req, operator_id)
        results.append(result)
    return results


def get_test_run(db: Session, run_id: int) -> TestRunResponse:
    record = prompt_test_run_repo.get_by_id(db, run_id)
    if record is None:
        raise AppException(code=404001, message="测试运行记录不存在")

    evaluations = []
    if record.evaluations:
        evaluations = [
            EvaluationResponse.model_validate(e) for e in record.evaluations
        ]

    return TestRunResponse(
        id=record.id,
        prompt_id=record.prompt_id,
        version_id=record.version_id,
        test_case_id=record.test_case_id,
        model_name=record.model_name,
        input_data=record.input_data,
        rendered_prompt=record.rendered_prompt,
        raw_output=record.raw_output,
        structured_output=record.structured_output,
        token_usage=record.token_usage,
        latency=record.latency,
        trace_id=record.trace_id,
        status=record.status,
        evaluations=evaluations,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def list_test_runs(
    db: Session, prompt_id: int, page: int = 1, page_size: int = 20,
) -> tuple[list[TestRunResponse], int]:
    offset = (page - 1) * page_size
    items, total = prompt_test_run_repo.get_by_prompt(db, prompt_id, offset=offset, limit=page_size)
    return [get_test_run(db, r.id) for r in items], total


def _build_test_prompt(version: PromptVersion, input_data: dict) -> list[dict]:
    from app.modules.prompt_center.application.prompt_render_service import _build_business_content, _build_messages

    system_content = version.system_content or ""
    business_content = _build_business_content(version)

    context_parts: list[str] = []
    for key, val in input_data.items():
        if key != "user_question" and val is not None:
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False, indent=2)
            context_parts.append(f"{key}：\n{val}")

    runtime_context = "\n\n".join(context_parts)
    user_question = input_data.get("user_question", "")

    return _build_messages(system_content, business_content, runtime_context, user_question)


def _messages_to_text(messages: list[dict]) -> str:
    parts: list[str] = []
    for msg in messages:
        parts.append(f"[{msg['role']}]\n{msg['content']}")
    return "\n\n---\n\n".join(parts)


def _get_system_text(messages: list[dict]) -> str | None:
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    return None


def _get_user_text(messages: list[dict]) -> str:
    for msg in messages:
        if msg["role"] == "user":
            return msg["content"]
    return ""


def _try_parse_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
