from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.operation_agent.repositories.analysis_record_repo import analysis_record_repo
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.models import ReportChatMessage
from app.runtime.models.trace_model import AiTrace
from sqlalchemy import select

router = APIRouter()


def _event_out(event: object) -> dict:
    return {
        "id": getattr(event, "event_id", ""),
        "sequence": getattr(event, "sequence", 0),
        "event_type": getattr(event, "event_type", ""),
        "node_key": getattr(event, "node_key", None),
        "node_name": getattr(event, "node_name", None),
        "status": getattr(event, "status", None),
        "message": getattr(event, "message", None),
        "duration_ms": getattr(event, "duration_ms", None),
        "source_label": getattr(event, "source_label", None),
        "payload": getattr(event, "payload_json", None),
        "error_code": getattr(event, "error_code", None),
        "error_message": getattr(event, "error_message", None),
        "timestamp": getattr(event, "event_timestamp", None),
    }


def _trace_out(trace: AiTrace) -> dict:
    return {
        "id": trace.id,
        "trace_id": trace.trace_id,
        "span_id": trace.span_id,
        "parent_span_id": trace.parent_span_id,
        "session_id": trace.session_id,
        "span_type": trace.span_type,
        "graph_name": trace.graph_name,
        "node_name": trace.node_name,
        "tool_name": trace.tool_name,
        "model_name": trace.model_name,
        "prompt_code": trace.prompt_code,
        "prompt_version": trace.prompt_version,
        "input_data": trace.input_data,
        "output_data": trace.output_data,
        "cost_ms": trace.cost_ms,
        "prompt_tokens": trace.prompt_tokens,
        "completion_tokens": trace.completion_tokens,
        "total_tokens": trace.total_tokens,
        "status": trace.status,
        "error_message": trace.error_message,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }


@router.get("/operation/graph-runs", response_model=ApiResponse[list[dict]])
def list_graph_runs(
    graph_type: str | None = Query(default=None, pattern="^(report_generation|report_chat)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    runs: list[dict] = []
    if graph_type in (None, "report_generation"):
        for record in analysis_record_repo.list_recent(db, limit=page_size * 2):
            runs.append({
                "run_id": str(record.id),
                "graph_type": "report_generation",
                "graph_name": "ioc_operation_analysis_graph",
                "title": record.report_name or "运营分析报告",
                "status": record.status,
                "trace_id": record.trace_id,
                "session_id": None,
                "summary": record.summary_text,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            })
    if graph_type in (None, "report_chat"):
        for session in report_chat_repo.list_recent_sessions(db, limit=page_size * 2):
            latest_message = db.scalar(
                select(ReportChatMessage)
                .where(ReportChatMessage.session_id == session.id)
                .order_by(ReportChatMessage.created_at.desc())
                .limit(1)
            )
            runs.append({
                "run_id": session.id,
                "graph_type": "report_chat",
                "graph_name": "ioc_report_chat_graph",
                "title": session.title,
                "status": session.status,
                "trace_id": latest_message.trace_id if latest_message else None,
                "session_id": session.id,
                "summary": latest_message.content if latest_message else None,
                "created_at": session.updated_at.isoformat() if session.updated_at else None,
            })
    runs.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    start = (page - 1) * page_size
    return ApiResponse(data=runs[start : start + page_size])


@router.get("/operation/graph-runs/{graph_type}/{run_id}", response_model=ApiResponse[dict])
def get_graph_run_detail(
    graph_type: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    if graph_type == "report_generation":
        record = analysis_record_repo.get_by_id(db, int(run_id))
        if record is None:
            return ApiResponse(code=404001, message="报告生成记录不存在")
        return ApiResponse(data={
            "run_id": run_id,
            "graph_type": graph_type,
            "graph_name": "ioc_operation_analysis_graph",
            "title": record.report_name or "运营分析报告",
            "status": record.status,
            "trace_id": record.trace_id,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "input": record.input_snapshot_json,
            "output": {
                "summary": record.summary_text,
                "report": record.final_answer_markdown,
                "abnormal_items": record.abnormal_items_json,
                "risk_items": record.risk_items_json,
                "advice_items": record.advice_items_json,
                "evidence": record.evidence_json,
            },
            "events": [_event_out(event) for event in analysis_record_repo.list_events(db, record.trace_id)],
            "traces": [],
        })

    if graph_type == "report_chat":
        session = report_chat_repo.get_session(db, run_id)
        if session is None:
            return ApiResponse(code=404001, message="报告追问记录不存在")
        messages = report_chat_repo.list_messages(db, run_id)
        trace_ids = {message.trace_id for message in messages if message.trace_id}
        traces: list[AiTrace] = []
        for trace_id in trace_ids:
            traces.extend(db.scalars(select(AiTrace).where(AiTrace.trace_id == trace_id)).all())
        return ApiResponse(data={
            "run_id": run_id,
            "graph_type": graph_type,
            "graph_name": "ioc_report_chat_graph",
            "title": session.title,
            "status": session.status,
            "trace_id": next(iter(trace_ids), None),
            "created_at": session.updated_at.isoformat() if session.updated_at else None,
            "input": {"report_id": session.report_id, "user_id": session.user_id},
            "output": {"message_count": len(messages)},
            "events": [{
                "id": message.id,
                "sequence": index + 1,
                "event_type": "user_question" if message.role == "user" else "assistant_answer",
                "node_name": "报告追问",
                "status": "success",
                "message": message.content,
                "timestamp": message.created_at.isoformat() if message.created_at else None,
                "payload": {
                    "runtime_session_id": message.runtime_session_id,
                    "question_scope": message.question_scope,
                    "answer_type": message.answer_type,
                    "evidence_refs": message.evidence_refs,
                    "query_scope": message.query_scope,
                    "trace_id": message.trace_id,
                },
            } for index, message in enumerate(messages)],
            "traces": [_trace_out(trace) for trace in traces],
        })

    return ApiResponse(code=400001, message="不支持的 Graph 类型")


class AnalysisRecordOut(BaseModel):
    id: int
    trace_id: str
    report_name: str | None
    domain: str
    time_dimension: str | None
    analysis_date: str | None
    status: str
    summary_text: str | None
    final_answer_markdown: str | None
    page_context: dict | None
    advice_items_json: dict | None
    evidence_json: dict | None
    created_at: str | None


@router.get("/operation/records", response_model=ApiResponse[list[dict]])
def list_records(
    domain: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    records = analysis_record_repo.list_recent(
        db, domain=domain, user_id=user_id, limit=page_size, offset=(page - 1) * page_size
    )
    data = []
    for r in records:
        data.append({
            "id": r.id,
            "trace_id": r.trace_id,
            "report_name": r.report_name,
            "domain": r.domain,
            "time_dimension": r.time_dimension,
            "analysis_date": r.analysis_date,
            "status": r.status,
            "summary_text": r.summary_text,
            "final_answer_markdown": r.final_answer_markdown,
            "page_context": r.page_context_json,
            "advice_items": r.advice_items_json,
            "evidence": r.evidence_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return ApiResponse(data=data)


@router.get("/operation/records/{record_id}", response_model=ApiResponse[dict])
def get_record_detail(record_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    record = analysis_record_repo.get_by_id(db, record_id)
    if record is None:
        return ApiResponse(code=404001, message="记录不存在")
    return ApiResponse(data={
        "id": record.id,
        "trace_id": record.trace_id,
        "report_name": record.report_name,
        "domain": record.domain,
        "time_dimension": record.time_dimension,
        "analysis_date": record.analysis_date,
        "status": record.status,
        "error_message": record.error_message,
        "summary_text": record.summary_text,
        "final_answer_markdown": record.final_answer_markdown,
        "page_context": record.page_context_json,
        "abnormal_items": record.abnormal_items_json,
        "risk_items": record.risk_items_json,
        "advice_items": record.advice_items_json,
        "evidence": record.evidence_json,
        "analysis_basis": (record.evidence_json or {}).get("analysis_basis", {}),
        "model_name": record.model_name,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.total_tokens,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    })


@router.get("/operation/records/{record_id}/download")
def download_record(record_id: int, db: Session = Depends(get_db)):
    record = analysis_record_repo.get_by_id(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    filename = _markdown_filename(record.report_name or "运营分析报告")
    content = record.final_answer_markdown or "# 无内容"
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(filename),
    )


def _markdown_filename(name: str) -> str:
    """生成安全的 Markdown 文件名，避免路径字符和空文件名影响下载。"""
    cleaned = "".join(ch if ch not in '\\/:*?"<>|\r\n' else "_" for ch in name).strip()
    if not cleaned:
        cleaned = "运营分析报告"
    return cleaned if cleaned.lower().endswith(".md") else f"{cleaned}.md"


def _download_headers(filename: str) -> dict[str, str]:
    """构造兼容中文文件名的下载头。

    HTTP 头需要能编码为 latin-1。中文文件名通过 filename* 按 RFC 5987 编码，
    filename 保留 ASCII fallback，避免 Starlette 在响应头编码阶段抛 UnicodeEncodeError。
    """
    encoded = quote(filename, safe="")
    return {
        "Content-Disposition": (
            f'attachment; filename="operation-report.md"; filename*=UTF-8\'\'{encoded}'
        ),
    }
