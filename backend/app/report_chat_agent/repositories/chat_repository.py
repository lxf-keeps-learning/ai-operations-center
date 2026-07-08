from sqlalchemy import select
from sqlalchemy.orm import Session

from app.report_chat_agent.models import ReportChatMessage, ReportChatSession
from app.utils.ids import new_message_id, new_session_id
from app.utils.timezone import now_local


class ReportChatRepository:
    def create_session(
        self,
        db: Session,
        *,
        report_id: int,
        user_id: str,
        title: str = "本质安全报告追问",
        scene: str = "essential_safety",
        session_id: str | None = None,
    ) -> ReportChatSession:
        session = ReportChatSession(
            id=session_id or new_session_id(),
            report_id=report_id,
            user_id=user_id,
            title=title,
            scene=scene,
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_or_create_session(
        self,
        db: Session,
        *,
        report_id: int,
        user_id: str,
        title: str = "本质安全报告追问",
        scene: str = "essential_safety",
    ) -> ReportChatSession:
        existing = self.get_recent_session(db, report_id=report_id, user_id=user_id)
        if existing is not None:
            return existing

        return self.create_session(
            db,
            report_id=report_id,
            user_id=user_id,
            title=title,
            scene=scene,
        )

    def ensure_session(
        self,
        db: Session,
        *,
        session_id: str,
        report_id: int,
        user_id: str,
        title: str = "本质安全报告追问",
        scene: str = "essential_safety",
    ) -> ReportChatSession:
        existing = self.get_session(db, session_id)
        if existing is not None:
            return existing
        return self.create_session(
            db,
            session_id=session_id,
            report_id=report_id,
            user_id=user_id,
            title=title,
            scene=scene,
        )

    def get_recent_session(
        self,
        db: Session,
        *,
        report_id: int,
        user_id: str,
    ) -> ReportChatSession | None:
        stmt = (
            select(ReportChatSession)
            .where(
                ReportChatSession.report_id == report_id,
                ReportChatSession.user_id == user_id,
                ReportChatSession.status == "active",
            )
            .order_by(ReportChatSession.updated_at.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    def get_session(self, db: Session, session_id: str) -> ReportChatSession | None:
        return db.get(ReportChatSession, session_id)

    def touch_session(self, db: Session, session_id: str) -> None:
        session = self.get_session(db, session_id)
        if session is None:
            return
        session.updated_at = now_local()
        db.commit()

    def create_message(
        self,
        db: Session,
        *,
        session_id: str,
        report_id: int,
        role: str,
        content: str,
        trace_id: str | None = None,
        question_scope: str | None = None,
        answer_type: str | None = None,
        evidence_refs: list[str] | None = None,
        query_scope: dict | None = None,
        used_rag: bool = False,
        rag_source_refs: list[str] | None = None,
        rag_sources: list[dict] | None = None,
    ) -> ReportChatMessage:
        message = ReportChatMessage(
            id=new_message_id(),
            session_id=session_id,
            report_id=report_id,
            role=role,
            content=content,
            trace_id=trace_id,
            question_scope=question_scope,
            answer_type=answer_type,
            evidence_refs=evidence_refs or [],
            query_scope=_with_rag_refs(query_scope, used_rag, rag_source_refs, rag_sources),
        )
        db.add(message)

        session = self.get_session(db, session_id)
        if session is not None:
            session.updated_at = now_local()

        db.commit()
        db.refresh(message)
        return message

    def list_messages(self, db: Session, session_id: str) -> list[ReportChatMessage]:
        stmt = (
            select(ReportChatMessage)
            .where(ReportChatMessage.session_id == session_id)
            .order_by(ReportChatMessage.created_at.asc(), ReportChatMessage.id.asc())
        )
        return list(db.scalars(stmt).all())


report_chat_repo = ReportChatRepository()


def _with_rag_refs(
    query_scope: dict | None,
    used_rag: bool,
    rag_source_refs: list[str] | None,
    rag_sources: list[dict] | None,
) -> dict:
    """把 RAG 展示字段写入既有 query_scope，兼容未迁移的本地旧表。"""
    result = dict(query_scope or {})
    refs = rag_source_refs or []
    sources = rag_sources or []
    if used_rag or refs or sources:
        result["used_rag"] = bool(used_rag)
        result["rag_source_refs"] = refs
        result["rag_sources"] = sources
    return result
