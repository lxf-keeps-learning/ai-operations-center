from sqlalchemy import select
from sqlalchemy.orm import Session

from app.report_chat_agent.models import ReportChatMessage, ReportChatSession
from app.runtime.models.conversation_model import AiConversation
from app.runtime.models.session_model import AiSession
from app.runtime.schemas.status import CONV_ACTIVE, SESS_FAILED, SESS_RUNNING, SESS_SUCCESS
from app.utils.ids import new_conversation_id, new_message_id, new_session_id
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
        conversation = AiConversation(
            id=new_conversation_id(),
            user_id=user_id,
            title=title,
            biz_type="report_chat",
            source="report_chat_agent",
            status=CONV_ACTIVE,
            meta={"report_id": report_id, "scene": scene},
        )
        session = ReportChatSession(
            id=session_id or new_session_id(),
            conversation_id=conversation.id,
            report_id=report_id,
            user_id=user_id,
            title=title,
            scene=scene,
            status="active",
        )
        db.add_all([conversation, session])
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
            self.ensure_conversation(db, existing)
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

    def ensure_conversation(
        self,
        db: Session,
        session: ReportChatSession,
    ) -> AiConversation:
        """为迁移前的报告会话补建统一 Conversation 关联。"""
        if session.conversation_id:
            existing = db.get(AiConversation, session.conversation_id)
            if existing is not None:
                return existing

        conversation = AiConversation(
            id=new_conversation_id(),
            user_id=session.user_id,
            title=session.title,
            biz_type="report_chat",
            source="report_chat_agent",
            status=CONV_ACTIVE,
            meta={"report_id": session.report_id, "scene": session.scene},
        )
        db.add(conversation)
        session.conversation_id = conversation.id
        db.commit()
        db.refresh(conversation)
        return conversation

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
        runtime_session_id: str | None = None,
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
            runtime_session_id=runtime_session_id,
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

    def begin_turn(
        self,
        db: Session,
        *,
        session: ReportChatSession,
        question: str,
        trace_id: str,
    ) -> AiSession:
        """原子保存用户问题，并创建统一 Runtime Session 运行记录。"""
        conversation = self.ensure_conversation(db, session)
        runtime_session = AiSession(
            id=new_session_id(),
            conversation_id=conversation.id,
            user_id=session.user_id,
            task_type="report_chat",
            input_text=question,
            context={
                "report_id": session.report_id,
                "report_chat_session_id": session.id,
                "trace_id": trace_id,
            },
            status=SESS_RUNNING,
            started_at=now_local(),
        )
        user_message = ReportChatMessage(
            id=new_message_id(),
            session_id=session.id,
            runtime_session_id=runtime_session.id,
            report_id=session.report_id,
            role="user",
            content=question,
            trace_id=trace_id,
            evidence_refs=[],
            query_scope={},
        )
        session.updated_at = now_local()
        db.add_all([runtime_session, user_message])
        db.commit()
        db.refresh(runtime_session)
        return runtime_session

    def complete_turn(
        self,
        db: Session,
        *,
        session_id: str,
        runtime_session_id: str,
        report_id: int,
        content: str,
        trace_id: str,
        question_scope: str | None,
        answer_type: str | None,
        evidence_refs: list[str] | None,
        query_scope: dict | None,
        used_rag: bool,
        rag_source_refs: list[str] | None,
        rag_sources: list[dict] | None,
    ) -> ReportChatMessage:
        """原子保存 AI 回答，并把统一 Runtime Session 标记为成功。"""
        runtime_session = db.get(AiSession, runtime_session_id)
        if runtime_session is None:
            raise ValueError(f"Runtime Session 不存在: {runtime_session_id}")

        message = ReportChatMessage(
            id=new_message_id(),
            session_id=session_id,
            runtime_session_id=runtime_session_id,
            report_id=report_id,
            role="assistant",
            content=content,
            trace_id=trace_id,
            question_scope=question_scope,
            answer_type=answer_type,
            evidence_refs=evidence_refs or [],
            query_scope=_with_rag_refs(query_scope, used_rag, rag_source_refs, rag_sources),
        )
        runtime_session.output_text = content
        runtime_session.status = SESS_SUCCESS
        runtime_session.error_message = None
        runtime_session.finished_at = now_local()
        session = self.get_session(db, session_id)
        if session is not None:
            session.updated_at = now_local()
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def fail_turn(
        self,
        db: Session,
        *,
        runtime_session_id: str,
        error_message: str,
    ) -> None:
        """保留已写入的用户问题，并记录本轮执行失败原因。"""
        runtime_session = db.get(AiSession, runtime_session_id)
        if runtime_session is None:
            return
        runtime_session.status = SESS_FAILED
        runtime_session.error_message = error_message[:65535]
        runtime_session.finished_at = now_local()
        db.commit()

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
