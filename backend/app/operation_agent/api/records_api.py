from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.operation_agent.repositories.analysis_record_repo import analysis_record_repo

router = APIRouter()


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
