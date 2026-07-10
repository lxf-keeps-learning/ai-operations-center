"""TraceService — 全链路追踪业务逻辑

记录每次用户请求在系统各环节（对话创建 → Prompt加载 → LLM调用 → 工具调用等）
的耗时和元信息，用于监控、诊断和性能分析。

Trace span 层级结构：
  trace_id (全局唯一请求 ID)
  ├── runtime  span (RuntimeService 整体耗时)
  ├── llm      span (LLM API 调用耗时)
  ├── tool     span (各工具调用耗时)
  └── graph    span (LangGraph 整体耗时)
"""

from sqlalchemy.orm import Session

from app.runtime.repositories.trace_repository import TraceRepository
from app.runtime.schemas.trace_schema import TraceCreate, TraceResponse

_repo = TraceRepository()


class TraceService:
    def create(self, db: Session, payload: TraceCreate) -> TraceResponse:
        """记录一条追踪 span（包含阶段名、开始/结束时间、耗时、元数据等）"""
        record = _repo.create(db, payload)
        return TraceResponse.model_validate(record)

    def list_by_trace_id(self, db: Session, trace_id: str) -> list[TraceResponse]:
        """按 trace_id 查询某次请求的全部 span（全链路聚合）"""
        records = _repo.list_by_trace_id(db, trace_id)
        return [TraceResponse.model_validate(r) for r in records]

    def list_by_session_id(self, db: Session, session_id: str) -> list[TraceResponse]:
        """按 session_id 查询某次会话涉及的所有追踪记录"""
        records = _repo.list_by_session_id(db, session_id)
        return [TraceResponse.model_validate(r) for r in records]


trace_service = TraceService()
