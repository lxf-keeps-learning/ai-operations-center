"""Build layered evidence for operation-analysis conclusions."""

from typing import Any

from app.operation_agent.state import OperationState


def build_analysis_basis(state: OperationState) -> dict[str, Any]:
    """Separate observed facts, analytical hypotheses, and knowledge evidence.

    The regular Operation Graph does not call RAG. Therefore knowledge_evidence
    remains empty and the result explicitly says so instead of implying that
    business data also proves a policy, SOP, or remediation method.
    """

    abnormal = state.get("abnormal_items", [])
    data_evidence = _deduplicate_evidence(state.get("evidence", []))
    reason = state.get("reason_analysis", "").strip()
    errors = state.get("errors", [])
    reason_degraded = any(item.get("node") == "analyze_reason" for item in errors)
    advice_degraded = any(item.get("node") == "generate_advice" for item in errors)

    facts = [
        {
            "conclusion_type": "fact",
            "statement": item.get("message", ""),
            "confidence": 0.95,
            "record_id": item.get("record_id"),
            "data_evidence": item.get("evidence", []),
        }
        for item in abnormal
        if item.get("message")
    ]

    hypotheses = []
    if abnormal and reason:
        hypotheses.append(
            {
                "conclusion_type": "hypothesis",
                "statement": reason,
                "confidence": 0.45 if reason_degraded else 0.65,
                "data_evidence": data_evidence,
                "knowledge_evidence": [],
            }
        )

    assumptions = []
    if abnormal:
        assumptions = [
            "当前原因分析仅依据本次业务数据、规则识别结果和记录间关联，尚未经过现场核查。",
            "当前常规报告未检索制度、标准、SOP、设备手册或历史案例，不将分析推测表述为已确认根因。",
        ]

    verification_steps = _verification_steps(abnormal)
    return {
        "schema_version": "1.0",
        "data_evidence": data_evidence,
        "knowledge_evidence": [],
        "knowledge_status": "not_used",
        "knowledge_note": "本次为常规业务数据分析，未调用 RAG；制度、标准、SOP 或案例依据需按需检索。",
        "facts": facts,
        "hypotheses": hypotheses,
        "assumptions": assumptions,
        "verification_steps": verification_steps,
        "reasoning_confidence": 0.45 if reason_degraded else 0.65 if abnormal else 0.95,
        "advice_confidence": 0.45 if advice_degraded else 0.6 if abnormal else 0.95,
    }


def _verification_steps(abnormal: list[dict[str, Any]]) -> list[str]:
    steps: list[str] = []
    for item in abnormal[:5]:
        name = item.get("metric_name") or item.get("message") or "异常项"
        record_id = item.get("record_id")
        suffix = f"（记录 {record_id}）" if record_id else ""
        step = f"核对{name}对应的原始记录、时间范围与现场情况{suffix}，确认异常口径和实际原因。"
        if step not in steps:
            steps.append(step)
    if abnormal:
        steps.append("由责任岗位确认根因和整改措施后，再进入执行或工单确认流程。")
    return steps


def _deduplicate_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in evidence:
        key = (
            str(item.get("source", "")),
            str(item.get("record_id", "")),
            str(item.get("description", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
