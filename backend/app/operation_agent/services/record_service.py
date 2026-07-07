from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.operation_agent.models.analysis_record_model import OperationAnalysisRecord
from app.operation_agent.repositories.analysis_record_repo import analysis_record_repo
from app.utils.timezone import now_local


def build_cache_key(page_context: dict) -> str:
    domain = page_context.get("domain", "")
    time_dim = page_context.get("time_dimension", "")
    date = page_context.get("date", "")
    company = page_context.get("company_id", "")
    project = page_context.get("project_id", "")
    return f"op:{domain}:{time_dim}:{date}:{company}:{project}"


def get_cached_result(db: Session, page_context: dict) -> OperationAnalysisRecord | None:
    cache_key = build_cache_key(page_context)
    record = analysis_record_repo.get_by_cache_key(db, cache_key)
    if record and record.created_at:
        age = (now_local() - record.created_at).total_seconds()
        if age < 1800:
            return record
    return None


def save_analysis_result(
    db: Session,
    *,
    trace_id: str,
    page_context: dict,
    input_snapshot: dict,
    result: dict[str, Any],
    status: str,
    error_message: str | None = None,
    user_context: dict | None = None,
) -> OperationAnalysisRecord:
    cache_key = build_cache_key(page_context)
    domain = page_context.get("domain", "safety")
    time_dim = page_context.get("time_dimension", "")
    analysis_date = page_context.get("date", "")
    company = page_context.get("company_id", "")
    project = page_context.get("project_id", "")
    trigger = page_context.get("trigger_type") or page_context.get("trigger_type", "tab_analysis")

    domain_label = {"safety": "本质安全", "maintenance": "设备运维", "business": "经营改善", "capability": "能力提升"}
    report_name = f"{domain_label.get(domain, domain)}运营分析报告"

    abnormal = result.get("abnormal_items", [])
    risk = result.get("risk_items", [])
    advice = result.get("advice_items", [])
    evidence = result.get("evidence", [])
    final_answer = result.get("final_answer", "")
    metrics = result.get("metrics", [])

    summary = ""
    if final_answer:
        for line in final_answer.split("\n"):
            if line.startswith("本次对"):
                summary = line.strip()
                break

    record = OperationAnalysisRecord(
        trace_id=trace_id,
        user_id=(user_context or {}).get("user_id"),
        tenant_id=(user_context or {}).get("tenant_id"),
        user_name=(user_context or {}).get("user_name"),
        report_name=report_name,
        report_type="operation_analysis",
        trigger_type=trigger,
        analysis_mode=page_context.get("analysis_mode", "domain_focus"),
        domain=domain,
        time_dimension=time_dim,
        analysis_date=analysis_date,
        start_time=now_local(),
        end_time=now_local(),
        company_id=company,
        project_id=project,
        page_context_json=page_context,
        input_snapshot_json=input_snapshot,
        metrics_json={"items": metrics},
        abnormal_items_json={"items": abnormal},
        risk_items_json={"items": risk},
        advice_items_json={"items": advice},
        evidence_json={"items": evidence},
        final_answer_markdown=final_answer,
        summary_text=summary,
        status=status,
        error_message=error_message,
        cache_key=cache_key,
        model_name="deepseek-chat",
    )
    return analysis_record_repo.create(db, record)
