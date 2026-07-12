"""Skill 执行适配层：将 Skill 转发给现有 Service/Graph。"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.service import analyze_operation
from app.report_chat_agent.service import send_chat_message
from app.skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillExecutionResult,
    SkillRiskLevel,
)
from app.utils.ids import new_trace_id

SkillExecutor = Callable[
    [SkillDefinition, dict[str, Any], SkillExecutionContext],
    SkillExecutionResult,
]


class ReportDeepAnswerInput(BaseModel):
    session_id: str = Field(min_length=1)
    report_id: int = Field(gt=0)
    question: str = Field(min_length=1, max_length=2000)


def execute_skill(
    definition: SkillDefinition,
    inputs: dict[str, Any],
    context: SkillExecutionContext,
) -> SkillExecutionResult:
    if definition.risk_level != SkillRiskLevel.READ_ONLY or definition.side_effects.business_write:
        raise RuntimeError(f"Skill is not allowed by the read-only executor: {definition.id}")
    _validate_declared_inputs(definition, inputs)
    executor = _EXECUTORS.get(definition.executor_id)
    if executor is None:
        raise RuntimeError(f"Skill executor not found: {definition.executor_id}")
    return executor(definition, inputs, context)


def _validate_declared_inputs(
    definition: SkillDefinition,
    inputs: dict[str, Any],
) -> None:
    declared = set(definition.required_inputs) | set(definition.optional_inputs)
    missing = sorted(set(definition.required_inputs) - set(inputs))
    unknown = sorted(set(inputs) - declared)
    if missing:
        raise ValueError(f"Missing required skill inputs: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unsupported skill inputs: {', '.join(unknown)}")


def execute_operation_analysis(
    definition: SkillDefinition,
    inputs: dict[str, Any],
    context: SkillExecutionContext,
) -> SkillExecutionResult:
    request = OperationAnalyzeRequest.model_validate(inputs)
    state = analyze_operation(
        request,
        user_context={
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
            "roles": context.roles,
            "permissions": context.permissions,
        },
        trace_id=context.trace_id,
    )
    errors = state.get("errors", [])
    summary = state.get("final_answer", "")
    status = "failed" if errors and not summary else "partial" if errors else "success"
    return SkillExecutionResult(
        skill_id=definition.id,
        skill_version=definition.version,
        trace_id=state.get("trace_id") or context.trace_id or new_trace_id(),
        status=status,
        data={
            "record_id": state.get("record_id"),
            "summary": summary,
            "abnormal_items": state.get("abnormal_items", []),
            "risk_items": state.get("risk_items", []),
            "advice_items": state.get("advice_items", []),
            "evidence": state.get("evidence", []),
            "analysis_basis": state.get("analysis_basis", {}),
        },
        errors=errors,
    )


def execute_report_deep_answer(
    definition: SkillDefinition,
    inputs: dict[str, Any],
    context: SkillExecutionContext,
) -> SkillExecutionResult:
    request = ReportDeepAnswerInput.model_validate(inputs)
    state = send_chat_message(
        session_id=request.session_id,
        report_id=request.report_id,
        question=request.question,
        user_id=context.user_id,
        trace_id=context.trace_id,
    )
    errors = state.get("errors", [])
    answer = state.get("final_answer", "")
    status = "failed" if errors and not answer else "partial" if errors else "success"
    return SkillExecutionResult(
        skill_id=definition.id,
        skill_version=definition.version,
        trace_id=state.get("trace_id") or context.trace_id or new_trace_id(),
        status=status,
        data={
            "conversation_id": state.get("conversation_id", ""),
            "session_id": request.session_id,
            "runtime_session_id": state.get("runtime_session_id", ""),
            "message_id": state.get("message_id", ""),
            "answer": answer,
            "question_scope": state.get("question_scope", "report_internal"),
            "answer_type": state.get("answer_type", "normal"),
            "evidence_refs": state.get("evidence_refs", []),
            "query_scope": state.get("query_scope", {}),
            "used_rag": state.get("used_rag", False),
            "rag_source_refs": state.get("rag_source_refs", []),
            "rag_sources": state.get("rag_sources", []) or state.get("rag_results", []),
        },
        errors=errors,
    )


_EXECUTORS: dict[str, SkillExecutor] = {
    "operation_analysis_graph": execute_operation_analysis,
    "report_deep_answer_graph": execute_report_deep_answer,
}
