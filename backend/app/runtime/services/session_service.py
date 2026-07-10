"""SessionService — 运行记录（Session）业务逻辑

Session 是用户单次提问的完整运行记录，包含输入文本、输出文本、状态和耗时等。
每次用户发送消息都会创建一个 Session，LLM 返回后更新输出和状态。
Session 也承担了"消息"的职责：通过 list_recent_messages 将历史 Session
拼接为 user/assistant 格式的消息列表，供 LLM 上下文使用。
"""

from sqlalchemy.orm import Session

from app.runtime.repositories.session_repository import SessionRepository
from app.runtime.schemas.session_schema import SessionCreate, SessionResponse, SessionUpdate
from app.runtime.schemas.status import SESS_CANCELLED, SESS_SUCCESS

_repo = SessionRepository()


class SessionService:
    def create(self, db: Session, payload: SessionCreate) -> SessionResponse:
        """创建新的运行记录，记录用户输入和元信息"""
        record = _repo.create(db, payload)
        return SessionResponse.model_validate(record)

    def get_by_id(self, db: Session, session_id: str) -> SessionResponse | None:
        """根据 Session ID 查询单条运行记录"""
        record = _repo.get_by_id(db, session_id)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def list_recent_messages(
        self,
        db: Session,
        conversation_id: str,
        limit: int = 6,
    ) -> list[dict[str, str]]:
        """
        查询指定会话中最近 limit 条成功的运行记录，
        拼接为 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        格式的消息列表，供 LLM 调用时作为历史上下文传入。
        """
        records = _repo.list_recent_success_by_conversation(db, conversation_id, limit)
        messages: list[dict[str, str]] = []
        for record in records:
            messages.append({"role": "user", "content": record.input_text})
            if record.output_text:
                messages.append({"role": "assistant", "content": record.output_text})
        return messages

    def update(
        self,
        db: Session,
        session_id: str,
        payload: SessionUpdate,
    ) -> SessionResponse | None:
        """更新运行记录（输出文本、状态、耗时等）"""
        record = _repo.update(db, session_id, payload)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def mark_success(self, db: Session, session_id: str) -> SessionResponse | None:
        """将运行记录标记为成功完成"""
        record = _repo.update_status(db, session_id, SESS_SUCCESS)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def mark_cancelled(self, db: Session, session_id: str) -> SessionResponse | None:
        """将运行记录标记为已取消（如用户中断或异常）"""
        record = _repo.update_status(db, session_id, SESS_CANCELLED)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def update_output(
        self,
        db: Session,
        session_id: str,
        output_text: str,
        status: str = SESS_SUCCESS,
    ) -> SessionResponse | None:
        """快捷方法：同时更新输出文本和状态"""
        return self.update(db, session_id, SessionUpdate(output_text=output_text, status=status))


session_service = SessionService()
